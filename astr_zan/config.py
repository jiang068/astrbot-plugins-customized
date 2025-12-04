"""
配置管理模块
"""
from astrbot.core.config.astrbot_config import AstrBotConfig


class ConfigManager:
    """配置管理器，负责管理插件的所有配置项"""
    
    def __init__(self, config: AstrBotConfig):
        self.config = config
        
        # 从配置读取各种回复消息
        self.success_responses: list[str] = config.get("success_responses", [])
        self.limit_responses: list[str] = config.get("limit_responses", [])
        self.stranger_responses: list[str] = config.get("stranger_responses", [])
        self.permission_responses: list[str] = config.get("permission_responses", [])

        # 群聊白名单
        self.enable_white_list_groups: bool = config.get(
            "enable_white_list_groups", False
        )
        self.white_list_groups: list[str] = config.get("white_list_groups", [])
