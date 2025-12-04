"""PDF转换模块

负责将下载的图片转换为PDF文件
"""
import os
import re
import asyncio
from typing import Optional

from astrbot.api import logger

try:
    import img2pdf
except ImportError:
    img2pdf = None


class PDFConverter:
    """PDF转换器"""
    
    def __init__(self, config_manager):
        """初始化PDF转换器
        
        Args:
            config_manager: 配置管理器实例
        """
        self.config_manager = config_manager
    
    async def convert_to_pdf(self, comic_id: str, source_dir: str, download_dir: str) -> Optional[str]:
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
        
        self.config_manager.log('info', f"开始收集图片文件，源目录: {source_dir}")
        
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
        self.config_manager.log('info', f"找到 {len(image_files)} 个图片文件")
        
        # 转换为PDF
        pdf_path = os.path.join(download_dir, f"jm_{comic_id}.pdf")
        
        try:
            # 直接使用img2pdf进行无损转换
            # img2pdf会自动处理JPEG、PNG等格式，无需手动转换
            # 对于RGBA等特殊格式，img2pdf会自动应用PNG Paeth过滤器
            self.config_manager.log('info', f"开始转换PDF，共 {len(image_files)} 张图片")
            
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
