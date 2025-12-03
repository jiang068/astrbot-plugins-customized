"""配置管理模块

负责管理插件配置的读取和日志输出
"""
import os
from astrbot.api import logger


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, plugin_config: dict):
        """初始化配置管理器
        
        Args:
            plugin_config: 插件配置字典
        """
        self.plugin_config = plugin_config
    
    def log(self, level: str, message: str, force: bool = False):
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
    
    def get_download_dir(self):
        """获取下载目录（每次动态读取配置）"""
        download_dir = self.plugin_config.get("download_dir")
        self.log('info', f"配置中的download_dir: {download_dir}")
        if not download_dir:
            download_dir = "./jm_downloads"
        if not os.path.isabs(download_dir):
            # 如果是相对路径，则相对于当前工作目录
            download_dir = os.path.join(os.getcwd(), download_dir)
        # 确保下载目录存在
        os.makedirs(download_dir, exist_ok=True)
        return download_dir
    
    def get_config_value(self, key: str, default=None):
        """动态获取配置值"""
        value = self.plugin_config.get(key)
        # 避免循环调用：如果是获取 log_level，直接返回不记录日志
        if key != 'log_level':
            self.log('info', f"获取配置 {key}: {value}, 默认值: {default}")
        # 只有当配置值为 None 时才使用默认值
        return value if value is not None else default
