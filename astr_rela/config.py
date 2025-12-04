"""
配置管理模块
管理插件配置和黑名单检查
"""
from astrbot.core.config.astrbot_config import AstrBotConfig


class ConfigManager:
    """配置管理器"""

    def __init__(self, config: AstrBotConfig, context):
        self.config = config
        self.context = context
        
        # 管理群ID，审批信息会发到此群
        self.manage_group: int = config.get("manage_group", 0)
        # 管理员QQ号列表，审批信息会私发给这些人
        self.admins_id: list[str] = list(set(context.get_config().get("admins_id", [])))
        # 最大允许禁言时长，超过自动退群
        self.max_ban_duration: int = config.get("max_ban_duration", 86400)
        # 群聊黑名单，bot不会再加入这些群
        self.group_blacklist: list[str] = config.get("group_blacklist", [])
        # 互斥成员列表，群内有这些人则自动退群
        self.mutual_blacklist: list[str] = config.get("mutual_blacklist", [])
        # 最大群容量，超过自动退群
        self.max_group_capacity: int = config.get("max_group_capacity", 100)
        # 是否自动抽查群消息
        self.auto_check_messages: bool = config.get("auto_check_messages", False)
        # 新群延迟抽查时间（秒）
        self.new_group_check_delay: int = config.get("new_group_check_delay", 600)
        # 是否启用自动通过好友申请
        self.enable_auto_approve: bool = config.get("enable_auto_approve", False)
        # 自动通过好友申请的关键词
        self.auto_approve_keyword: str = config.get("auto_approve_keyword", "")

    def is_group_in_blacklist(self, group_id) -> bool:
        """检查群是否在黑名单中（兼容字符串和数字）"""
        return any(str(group_id) == str(gid) for gid in self.group_blacklist)

    def add_to_blacklist(self, group_id):
        """将群加入黑名单"""
        if not self.is_group_in_blacklist(group_id):
            self.group_blacklist.append(str(group_id))
            self.config.save_config()

    def remove_from_blacklist(self, group_id):
        """将群从黑名单移除"""
        gid = str(group_id)
        if gid in self.group_blacklist:
            self.group_blacklist.remove(gid)
            self.config.save_config()
