"""任务执行模块

负责执行完整的下载和转换任务
"""
import os
import shutil
import tempfile
import asyncio

from astrbot.api.event import AstrMessageEvent
from astrbot.api import logger


class TaskExecutor:
    """任务执行器"""
    
    def __init__(self, config_manager, downloader, converter):
        """初始化任务执行器
        
        Args:
            config_manager: 配置管理器实例
            downloader: 下载器实例
            converter: PDF转换器实例
        """
        self.config_manager = config_manager
        self.downloader = downloader
        self.converter = converter
    
    async def execute_download_task(self, event: AstrMessageEvent, comic_id: str, send_progress: bool, download_dir: str):
        """执行下载任务的实际逻辑"""
        
        temp_dir = None
        pdf_path = None
        download_timeout = False
        
        try:
            # 创建临时目录用于下载
            temp_dir = tempfile.mkdtemp(prefix=f"jm_{comic_id}_", dir=download_dir)
            self.config_manager.log('info', f"临时下载目录: {temp_dir}")
            
            # 获取超时配置
            timeout_minutes = self.config_manager.get_config_value('task_timeout_minutes', 10)
            
            # 下载漫画（带超时控制）
            if timeout_minutes > 0:
                timeout_seconds = timeout_minutes * 60
                try:
                    await asyncio.wait_for(
                        self.downloader.download_comic(comic_id, temp_dir),
                        timeout=timeout_seconds
                    )
                    logger.info(f"漫画 {comic_id} 下载完成")
                except asyncio.TimeoutError:
                    download_timeout = True
                    logger.warning(f"漫画 {comic_id} 下载超时（{timeout_minutes}分钟），尝试转换已下载的图片")
                    if send_progress:
                        yield event.plain_result(f"⚠️ 下载任务超时（{timeout_minutes}分钟），尝试转换已下载的图片...")
            else:
                # 无超时限制
                await self.downloader.download_comic(comic_id, temp_dir)
                logger.info(f"漫画 {comic_id} 下载完成")
            
            if not download_timeout and send_progress:
                yield event.plain_result(f"✅ 下载完成，开始转换PDF...")
            
            # 转换为PDF
            pdf_path = await self.converter.convert_to_pdf(comic_id, temp_dir, download_dir)
            self.config_manager.log('info', f"PDF 转换完成: {pdf_path}")
            
            # 发送PDF文件
            if pdf_path and os.path.exists(pdf_path):
                pdf_size = os.path.getsize(pdf_path) / (1024 * 1024)  # MB
                
                # 动态读取文件大小限制配置
                max_file_size_mb = self.config_manager.get_config_value('max_file_size_mb', 0)
                # 检查文件大小限制
                if max_file_size_mb > 0 and pdf_size > max_file_size_mb:
                    yield event.plain_result(
                        f"⚠️ 警告: PDF文件过大 ({pdf_size:.2f} MB > {max_file_size_mb} MB)\n"
                        f"可能发送失败或需要较长时间"
                    )
                
                if send_progress:
                    if download_timeout:
                        yield event.plain_result(f"✅ 已将部分下载的图片转换为PDF ({pdf_size:.2f} MB)，准备发送...")
                    else:
                        yield event.plain_result(f"✅ PDF生成成功 ({pdf_size:.2f} MB)，准备发送...")
                
                # 使用消息链发送PDF文件
                from astrbot.api.message_components import File
                yield event.chain_result([File(file=pdf_path, name=f"jm_{comic_id}.pdf")])
                
                if download_timeout:
                    logger.warning(f"PDF已发送（部分内容，因超时）: {pdf_path}")
                    if send_progress:
                        yield event.plain_result("⚠️ 注意：此PDF仅包含超时前下载的部分图片")
                else:
                    logger.info(f"PDF已发送: {pdf_path}")
            else:
                if download_timeout:
                    yield event.plain_result("❌ 下载超时且未能找到可转换的图片")
                else:
                    yield event.plain_result("❌ PDF文件生成失败")
                
        except asyncio.TimeoutError:
            # 这个异常已在上面处理，不应该到这里
            logger.error(f"意外的超时异常: {comic_id}")
            yield event.plain_result(f"❌ 任务执行超时")
        except Exception as e:
            logger.error(f"处理漫画 {comic_id} 时出错: {str(e)}", exc_info=True)
            yield event.plain_result(f"❌ 处理失败: {str(e)}")
        
        finally:
            # 动态读取配置
            keep_images = self.config_manager.get_config_value('keep_images', False)
            keep_pdf = self.config_manager.get_config_value('keep_pdf', False)
            
            # 清理临时文件
            if not keep_images and temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                    self.config_manager.log('info', f"已清理临时目录: {temp_dir}")
                except Exception as e:
                    logger.warning(f"清理临时目录失败: {str(e)}")
            
            # 清理PDF文件（发送后）
            if not keep_pdf and pdf_path and os.path.exists(pdf_path):
                try:
                    os.remove(pdf_path)
                    self.config_manager.log('info', f"已清理PDF文件: {pdf_path}")
                except Exception as e:
                    logger.warning(f"清理PDF文件失败: {str(e)}")
