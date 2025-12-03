import os
import re
import shutil
import tempfile
import asyncio
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
        # 任务信号量（用于限制并发任务数）
        self._task_semaphore = None
        # 当前排队数（用于显示）
        self._queue_count = 0
        
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
    
    def _check_whitelist(self, event: AstrMessageEvent) -> bool:
        """检查用户和群组是否在白名单中
        
        Args:
            event: 消息事件
            
        Returns:
            True表示允许使用，False表示拒绝
        """
        # 获取白名单配置
        whitelist_groups_str = self._get_config_value('whitelist_groups', '')
        whitelist_users_str = self._get_config_value('whitelist_users', '')
        
        # 解析白名单（去除空格，过滤空字符串）
        whitelist_groups = set()
        if whitelist_groups_str:
            whitelist_groups = {g.strip() for g in whitelist_groups_str.split(',') if g.strip()}
        
        whitelist_users = set()
        if whitelist_users_str:
            whitelist_users = {u.strip() for u in whitelist_users_str.split(',') if u.strip()}
        
        # 获取当前用户和群组信息
        user_id = str(event.get_sender_id())
        group_id = str(event.message_obj.group_id) if event.message_obj.group_id else ""
        is_group = bool(group_id)
        
        # 详细日志
        logger.info(f"白名单检查 - 用户ID: {user_id}, 群组ID: {group_id}, 是否群聊: {is_group}")
        logger.info(f"白名单用户配置: {whitelist_users if whitelist_users else '空(允许所有用户)'}")
        logger.info(f"白名单群组配置: {whitelist_groups if whitelist_groups else '空(允许所有群组)'}")
        
        # 新逻辑：用户白名单和群组白名单独立判断
        
        # 1. 检查用户白名单
        user_pass = False
        if not whitelist_users:
            # 用户白名单为空 = 允许所有用户
            user_pass = True
            logger.info(f"用户白名单未配置，用户 {user_id} 通过")
        elif user_id in whitelist_users:
            # 用户在白名单中
            user_pass = True
            logger.info(f"✅ 用户 {user_id} 在白名单中")
        else:
            logger.warning(f"❌ 用户 {user_id} 不在白名单中")
        
        # 2. 检查群组白名单（仅群聊时需要检查）
        group_pass = False
        if not is_group:
            # 私聊消息，不需要检查群组白名单
            group_pass = True
            logger.info("私聊消息，跳过群组白名单检查")
        elif not whitelist_groups:
            # 群组白名单为空 = 允许所有群组
            group_pass = True
            logger.info(f"群组白名单未配置，群组 {group_id} 通过")
        elif group_id in whitelist_groups:
            # 群组在白名单中
            group_pass = True
            logger.info(f"✅ 群组 {group_id} 在白名单中")
        else:
            logger.warning(f"❌ 群组 {group_id} 不在白名单中")
        
        # 3. 两者都需要通过（AND 逻辑）
        result = user_pass and group_pass
        
        if result:
            logger.info(f"✅ 白名单检查通过")
        else:
            logger.warning(f"❌ 白名单检查失败")
        
        return result
        
    async def initialize(self):
        """插件初始化"""
        # 检查依赖
        if jmcomic is None:
            logger.error("jmcomic 模块未安装，请使用 pip install jmcomic 安装")
        if img2pdf is None:
            logger.error("img2pdf 模块未安装，请使用 pip install img2pdf 安装")
        
        # 初始化任务信号量
        max_concurrent = self._get_config_value('max_concurrent_tasks', 2)
        if max_concurrent > 0:
            self._task_semaphore = asyncio.Semaphore(max_concurrent)
            logger.info(f"任务并发限制: 最多 {max_concurrent} 个任务同时运行")
        else:
            self._task_semaphore = None
            logger.info("任务并发限制: 无限制")
        
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
        # 白名单检查
        if not self._check_whitelist(event):
            # 已经在 _check_whitelist 中记录了详细日志
            return
        
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
        
        # 任务队列控制
        if self._task_semaphore is not None:
            # 检查当前是否需要排队
            if self._task_semaphore.locked():
                self._queue_count += 1
                queue_position = self._queue_count
                logger.info(f"任务队列已满，用户 {event.get_sender_id()} 排队中，前方 {queue_position} 个任务")
                if send_progress:
                    yield event.plain_result(f"⏳ 当前下载任务较多，您的请求正在排队...\n📊 前方还有 {queue_position} 个任务")
                
                # 等待获取信号量
                async with self._task_semaphore:
                    self._queue_count -= 1
                    logger.info(f"用户 {event.get_sender_id()} 的任务开始执行")
                    if send_progress:
                        yield event.plain_result(f"✅ 轮到您了！开始下载漫画 {comic_id}...")
                    # 执行实际下载任务
                    async for result in self._execute_download_task(event, comic_id, send_progress, download_dir):
                        yield result
            else:
                # 直接获取信号量并执行
                async with self._task_semaphore:
                    logger.info(f"用户 {event.get_sender_id()} 的任务立即开始")
                    if send_progress:
                        yield event.plain_result(f"📥 开始下载漫画 {comic_id}，请稍候...")
                    async for result in self._execute_download_task(event, comic_id, send_progress, download_dir):
                        yield result
        else:
            # 没有并发限制，直接执行
            logger.info(f"开始处理漫画 ID: {comic_id}")
            if send_progress:
                yield event.plain_result(f"📥 开始下载漫画 {comic_id}，请稍候...")
            async for result in self._execute_download_task(event, comic_id, send_progress, download_dir):
                yield result
    
    async def _execute_download_task(self, event: AstrMessageEvent, comic_id: str, send_progress: bool, download_dir: str):
        """执行下载任务的实际逻辑"""
        
        temp_dir = None
        pdf_path = None
        download_timeout = False
        
        try:
            # 创建临时目录用于下载
            temp_dir = tempfile.mkdtemp(prefix=f"jm_{comic_id}_", dir=download_dir)
            self._log('info', f"临时下载目录: {temp_dir}")
            
            # 获取超时配置
            timeout_minutes = self._get_config_value('task_timeout_minutes', 10)
            
            # 下载漫画（带超时控制）
            if timeout_minutes > 0:
                timeout_seconds = timeout_minutes * 60
                try:
                    await asyncio.wait_for(
                        self._download_comic(comic_id, temp_dir),
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
                await self._download_comic(comic_id, temp_dir)
                logger.info(f"漫画 {comic_id} 下载完成")
            
            if not download_timeout and send_progress:
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
        
        # 使用 asyncio.to_thread 在后台线程运行阻塞的下载函数
        # 这样不会阻塞 AstrBot 的事件循环
        await asyncio.to_thread(jmcomic.download_album, comic_id, option)
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
            
            # 定义转换函数（在线程中运行）
            def convert_to_pdf_sync():
                with open(pdf_path, "wb") as f:
                    # 使用 rotation=img2pdf.Rotation.ifvalid 处理无效的EXIF方向值
                    f.write(img2pdf.convert(image_files, rotation=img2pdf.Rotation.ifvalid))
            
            # 使用 asyncio.to_thread 在后台线程运行 PDF 转换
            # 避免大量图片时阻塞事件循环
            await asyncio.to_thread(convert_to_pdf_sync)
            
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
