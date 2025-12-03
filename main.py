import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

try:
    import jmcomic
except ImportError:
    jmcomic = None

try:
    import img2pdf
except ImportError:
    img2pdf = None


@register("astr-jm2pdf", "YourName", "下载禁漫天堂漫画并转换为PDF", "1.0.0", "https://github.com/yourname/astr-jm2pdf")
class JM2PDFPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        # 保存插件配置
        self.plugin_config = config if config is not None else {}
        
    def _log(self, level: str, message: str, force: bool = False):
        """根据配置的日志级别输出日志
        
        Args:
            level: 日志级别 (info/warning/error)
            message: 日志消息
            force: 是否强制输出（无视日志级别配置）
        """
        # 直接读取配置，避免循环调用
        log_level_config = self.plugin_config.get('log_level', 'simple')
        
        # 强制输出或详细模式下输出所有日志
        if force or log_level_config == 'detailed':
            if level == 'info':
                logger.info(message)
            elif level == 'warning':
                logger.warning(message)
            elif level == 'error':
                logger.error(message)
    
    def _get_download_dir(self):
        """获取下载目录（每次动态读取配置）"""
        download_dir = self.plugin_config.get("download_dir")
        self._log('info', f"配置中的download_dir: {download_dir}")
        if not download_dir:
            download_dir = "./jm_downloads"
        if not os.path.isabs(download_dir):
            # 如果是相对路径，则相对于当前工作目录
            download_dir = os.path.join(os.getcwd(), download_dir)
        # 确保下载目录存在
        os.makedirs(download_dir, exist_ok=True)
        return download_dir
    
    def _get_config_value(self, key: str, default=None):
        """动态获取配置值"""
        value = self.plugin_config.get(key)
        # 避免循环调用：如果是获取 log_level，直接返回不记录日志
        if key != 'log_level':
            self._log('info', f"获取配置 {key}: {value}, 默认值: {default}")
        # 只有当配置值为 None 时才使用默认值
        return value if value is not None else default
        
    async def initialize(self):
        """插件初始化"""
        # 检查依赖
        if jmcomic is None:
            logger.error("jmcomic 模块未安装，请使用 pip install jmcomic 安装")
        if img2pdf is None:
            logger.error("img2pdf 模块未安装，请使用 pip install img2pdf 安装")
        
        # 获取配置并显示（强制输出，不受日志级别限制）
        logger.info("JM2PDF 插件初始化完成")
        self._log('info', f"插件配置内容: {self.plugin_config}")
        logger.info(f"下载目录: {self._get_download_dir()}")
        self._log('info', f"保留图片: {self._get_config_value('keep_images', False)}")
        self._log('info', f"保留PDF: {self._get_config_value('keep_pdf', False)}")
        proxy = self._get_config_value('proxy', '')
        if proxy:
            logger.info(f"使用代理: {proxy}")

    @filter.command("jm")
    async def download_jm_comic(self, event: AstrMessageEvent, comic_id: str):
        """下载禁漫天堂漫画并转换为PDF
        
        使用方法: /jm <漫画ID>
        示例: /jm 123456
        """
        # 检查依赖
        if jmcomic is None or img2pdf is None:
            yield event.plain_result("❌ 缺少必要的依赖库，请先安装 jmcomic 和 img2pdf")
            return
        
        # 验证漫画ID格式（应该是纯数字）
        if not re.match(r'^\d+$', comic_id):
            yield event.plain_result(f"❌ 无效的漫画ID格式: {comic_id}\n请输入纯数字ID，例如: /jm 123456")
            return
        
        # 读取配置：是否发送进度消息
        send_progress = self._get_config_value('send_progress_message', True)
        download_dir = self._get_download_dir()  # 动态获取下载目录
        
        # 检查是否已存在PDF文件
        expected_pdf_path = os.path.join(download_dir, f"jm_{comic_id}.pdf")
        if os.path.exists(expected_pdf_path):
            logger.info(f"发现已存在的PDF文件: {expected_pdf_path}")  # 关键日志，强制输出
            if send_progress:
                yield event.plain_result(f"� 检测到已下载的PDF，直接发送...")
            
            # 直接发送已存在的PDF
            pdf_size = os.path.getsize(expected_pdf_path) / (1024 * 1024)  # MB
            max_size = self._get_config_value('max_file_size_mb', 0)
            
            if max_size > 0 and pdf_size > max_size:
                yield event.plain_result(f"⚠️ PDF文件过大 ({pdf_size:.2f}MB > {max_size}MB)，无法发送")
                return
            
            logger.info(f"PDF已发送: {expected_pdf_path}")  # 关键日志，强制输出
            from astrbot.api.message_components import File
            yield event.chain_result([File(file=expected_pdf_path, name=f"jm_{comic_id}.pdf")])
            return
        
        logger.info(f"开始处理漫画 ID: {comic_id}")  # 关键日志，强制输出
        if send_progress:
            yield event.plain_result(f"📥 开始下载漫画 {comic_id}，请稍候...")
        
        temp_dir = None
        pdf_path = None
        
        try:
            # 创建临时目录用于下载
            temp_dir = tempfile.mkdtemp(prefix=f"jm_{comic_id}_", dir=download_dir)
            self._log('info', f"临时下载目录: {temp_dir}")
            
            # 下载漫画
            await self._download_comic(comic_id, temp_dir)
            logger.info(f"漫画 {comic_id} 下载完成")  # 关键日志，强制输出
            if send_progress:
                yield event.plain_result(f"✅ 下载完成，开始转换PDF...")
            
            # 转换为PDF
            pdf_path = await self._convert_to_pdf(comic_id, temp_dir, download_dir)
            self._log('info', f"PDF 转换完成: {pdf_path}")
            
            # 发送PDF文件
            if pdf_path and os.path.exists(pdf_path):
                pdf_size = os.path.getsize(pdf_path) / (1024 * 1024)  # MB
                
                # 动态读取文件大小限制配置
                max_file_size_mb = self._get_config_value('max_file_size_mb', 0)
                # 检查文件大小限制
                if max_file_size_mb > 0 and pdf_size > max_file_size_mb:
                    yield event.plain_result(
                        f"⚠️ 警告: PDF文件过大 ({pdf_size:.2f} MB > {max_file_size_mb} MB)\n"
                        f"可能发送失败或需要较长时间"
                    )
                
                if send_progress:
                    yield event.plain_result(f"✅ PDF生成成功 ({pdf_size:.2f} MB)，准备发送...")
                
                # 使用消息链发送PDF文件
                from astrbot.api.message_components import File
                yield event.chain_result([File(file=pdf_path, name=f"jm_{comic_id}.pdf")])
                logger.info(f"PDF已发送: {pdf_path}")  # 关键日志，强制输出
            else:
                yield event.plain_result("❌ PDF文件生成失败")
                
        except Exception as e:
            logger.error(f"处理漫画 {comic_id} 时出错: {str(e)}", exc_info=True)
            yield event.plain_result(f"❌ 处理失败: {str(e)}")
        
        finally:
            # 动态读取配置
            keep_images = self._get_config_value('keep_images', False)
            keep_pdf = self._get_config_value('keep_pdf', False)
            
            # 清理临时文件
            if not keep_images and temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                    self._log('info', f"已清理临时目录: {temp_dir}")
                except Exception as e:
                    logger.warning(f"清理临时目录失败: {str(e)}")
            
            # 清理PDF文件（发送后）
            if not keep_pdf and pdf_path and os.path.exists(pdf_path):
                try:
                    os.remove(pdf_path)
                    self._log('info', f"已清理PDF文件: {pdf_path}")
                except Exception as e:
                    logger.warning(f"清理PDF文件失败: {str(e)}")

    async def _download_comic(self, comic_id: str, download_path: str):
        """下载漫画到指定目录
        
        Args:
            comic_id: 漫画ID
            download_path: 下载目录
        """
        # 动态读取配置
        proxy = self._get_config_value('proxy', '')
        timeout = self._get_config_value('timeout', 60)
        client_impl = self._get_config_value('jm_client_impl', 'html')
        retry_times = self._get_config_value('jm_retry_times', 5)
        download_cache = self._get_config_value('download_cache', True)
        image_decode = self._get_config_value('image_decode', True)
        image_suffix = self._get_config_value('image_suffix', '')
        concurrent_images = self._get_config_value('concurrent_images', 30)
        concurrent_photos = self._get_config_value('concurrent_photos', 8)
        dir_rule = self._get_config_value('dir_rule', 'Bd/Ptitle')
        normalize_zh = self._get_config_value('normalize_zh', '')
        enable_jm_log = self._get_config_value('enable_jm_log', False)
        jm_cookies_avs = self._get_config_value('jm_cookies_avs', '')
        
        # 构建option配置字典
        option_dict = {
            'log': enable_jm_log,
            'dir_rule': {
                'base_dir': download_path,
                'rule': dir_rule,
            },
            'client': {
                'impl': client_impl,
                'retry_times': retry_times,
            },
            'download': {
                'cache': download_cache,
                'image': {
                    'decode': image_decode,
                },
                'threading': {
                    'image': concurrent_images,
                    'photo': concurrent_photos,
                }
            }
        }
        
        # 添加中文繁简转换配置
        if normalize_zh:
            option_dict['dir_rule']['normalize_zh'] = normalize_zh
        
        # 添加图片格式转换配置
        if image_suffix:
            option_dict['download']['image']['suffix'] = image_suffix
        
        # 设置代理和cookies
        postman_meta = {}
        if proxy:
            # 支持多种代理配置格式
            if proxy.lower() in ['system', 'clash', 'v2ray']:
                postman_meta['proxies'] = proxy.lower()
            else:
                postman_meta['proxies'] = {
                    'http': proxy,
                    'https': proxy
                }
        
        # 添加cookies配置
        if jm_cookies_avs:
            postman_meta['cookies'] = {
                'AVS': jm_cookies_avs
            }
        
        if postman_meta:
            option_dict['client']['postman'] = {
                'meta_data': postman_meta
            }
        
        # 设置超时
        if timeout and timeout != 60:  # 只有非默认值才设置
            if 'postman' not in option_dict['client']:
                option_dict['client']['postman'] = {'meta_data': {}}
            # JMComic 的超时配置需要在 postman 中设置
            option_dict['client']['postman']['timeout'] = timeout
        
        # 使用字典创建option
        option = jmcomic.JmModuleConfig.option_class().construct(option_dict)
        
        # 下载漫画（详细日志）
        self._log('info', f"开始下载漫画 {comic_id}")
        self._log('info', f"客户端类型: {client_impl}, 域名: 自动获取")
        self._log('info', f"并发: 图片={concurrent_images}, 章节={concurrent_photos}")
        self._log('info', f"下载目录: {download_path}")
        
        jmcomic.download_album(comic_id, option)
        # 下载完成由调用方记录关键日志

    async def _convert_to_pdf(self, comic_id: str, source_dir: str, download_dir: str) -> Optional[str]:
        """将下载的图片转换为PDF
        
        Args:
            comic_id: 漫画ID
            source_dir: 图片所在目录
            download_dir: PDF输出目录
            
        Returns:
            PDF文件路径，如果失败返回None
        """
        # 收集所有图片文件
        image_files = []
        image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tif', '.tiff')
        
        self._log('info', f"开始收集图片文件，源目录: {source_dir}")
        
        # 递归搜索所有图片文件
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                if file.lower().endswith(image_extensions):
                    image_files.append(os.path.join(root, file))
        
        if not image_files:
            logger.error(f"在 {source_dir} 中未找到图片文件")
            return None
        
        # 自然排序（确保页面顺序正确）
        image_files = self._natural_sort(image_files)
        self._log('info', f"找到 {len(image_files)} 个图片文件")
        
        # 转换为PDF
        pdf_path = os.path.join(download_dir, f"jm_{comic_id}.pdf")
        
        try:
            # 直接使用img2pdf进行无损转换
            # img2pdf会自动处理JPEG、PNG等格式，无需手动转换
            # 对于RGBA等特殊格式，img2pdf会自动应用PNG Paeth过滤器
            self._log('info', f"开始转换PDF，共 {len(image_files)} 张图片")
            with open(pdf_path, "wb") as f:
                # 使用 rotation=img2pdf.Rotation.ifvalid 处理无效的EXIF方向值
                f.write(img2pdf.convert(image_files, rotation=img2pdf.Rotation.ifvalid))
            
            logger.info(f"PDF转换成功: {pdf_path}")  # 关键日志，强制输出
            return pdf_path
            
        except Exception as e:
            logger.error(f"PDF转换失败: {str(e)}", exc_info=True)
            return None

    def _natural_sort(self, file_list: list) -> list:
        """自然排序文件列表（按数字大小排序而非字符串）
        
        Args:
            file_list: 文件路径列表
            
        Returns:
            排序后的文件列表
        """
        def natural_key(text):
            """生成自然排序的key"""
            return [int(c) if c.isdigit() else c.lower() 
                    for c in re.split(r'(\d+)', text)]
        
        return sorted(file_list, key=natural_key)

    async def terminate(self):
        """插件卸载时的清理工作"""
        logger.info("JM2PDF 插件已卸载")
