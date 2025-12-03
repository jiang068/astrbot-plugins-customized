import os
import re
import asyncio

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

# 导入模块
from config import ConfigManager
from permission import PermissionChecker
from downloader import ComicDownloader
from converter import PDFConverter
from task_executor import TaskExecutor

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
        
        # 初始化模块
        self.config_manager = ConfigManager(self.plugin_config)
        self.permission_checker = PermissionChecker(self.config_manager)
        self.downloader = ComicDownloader(self.config_manager)
        self.converter = PDFConverter(self.config_manager)
        self.task_executor = TaskExecutor(self.config_manager, self.downloader, self.converter)
        
    async def initialize(self):
        """插件初始化"""
        # 检查依赖
        if jmcomic is None:
            logger.error("jmcomic 模块未安装，请使用 pip install jmcomic 安装")
        if img2pdf is None:
            logger.error("img2pdf 模块未安装，请使用 pip install img2pdf 安装")
        
        # 初始化任务信号量
        max_concurrent = self.config_manager.get_config_value('max_concurrent_tasks', 2)
        if max_concurrent > 0:
            self._task_semaphore = asyncio.Semaphore(max_concurrent)
            logger.info(f"任务并发限制: 最多 {max_concurrent} 个任务同时运行")
        else:
            self._task_semaphore = None
            logger.info("任务并发限制: 无限制")
        
        # 获取配置并显示（强制输出，不受日志级别限制）
        logger.info("JM2PDF 插件初始化完成")
        self.config_manager.log('info', f"插件配置内容: {self.plugin_config}")
        logger.info(f"下载目录: {self.config_manager.get_download_dir()}")
        self.config_manager.log('info', f"保留图片: {self.config_manager.get_config_value('keep_images', False)}")
        self.config_manager.log('info', f"保留PDF: {self.config_manager.get_config_value('keep_pdf', False)}")
        proxy = self.config_manager.get_config_value('proxy', '')
        if proxy:
            logger.info(f"使用代理: {proxy}")

    @filter.command("jm")
    async def download_jm_comic(self, event: AstrMessageEvent, comic_id: str):
        """下载禁漫天堂漫画并转换为PDF
        
        使用方法: /jm <漫画ID>
        示例: /jm 123456
        """
        # 检查仅私聊模式
        should_block, tip_message = self.permission_checker.check_private_only(event)
        if should_block:
            yield event.plain_result(tip_message)
            return
        
        # 白名单检查
        if not self.permission_checker.check_whitelist(event):
            # 已经在 check_whitelist 中记录了详细日志
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
        send_progress = self.config_manager.get_config_value('send_progress_message', True)
        download_dir = self.config_manager.get_download_dir()  # 动态获取下载目录
        
        # 检查是否已存在PDF文件
        expected_pdf_path = os.path.join(download_dir, f"jm_{comic_id}.pdf")
        if os.path.exists(expected_pdf_path):
            logger.info(f"发现已存在的PDF文件: {expected_pdf_path}")  # 关键日志，强制输出
            if send_progress:
                yield event.plain_result(f"� 检测到已下载的PDF，直接发送...")
            
            # 直接发送已存在的PDF
            pdf_size = os.path.getsize(expected_pdf_path) / (1024 * 1024)  # MB
            max_size = self.config_manager.get_config_value('max_file_size_mb', 0)
            
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
                    async for result in self.task_executor.execute_download_task(event, comic_id, send_progress, download_dir):
                        yield result
            else:
                # 直接获取信号量并执行
                async with self._task_semaphore:
                    logger.info(f"用户 {event.get_sender_id()} 的任务立即开始")
                    if send_progress:
                        yield event.plain_result(f"📥 开始下载漫画 {comic_id}，请稍候...")
                    async for result in self.task_executor.execute_download_task(event, comic_id, send_progress, download_dir):
                        yield result
        else:
            # 没有并发限制，直接执行
            logger.info(f"开始处理漫画 ID: {comic_id}")
            if send_progress:
                yield event.plain_result(f"📥 开始下载漫画 {comic_id}，请稍候...")
            async for result in self.task_executor.execute_download_task(event, comic_id, send_progress, download_dir):
                yield result

    async def terminate(self):
        """插件卸载时的清理工作"""
        logger.info("JM2PDF 插件已卸载")
