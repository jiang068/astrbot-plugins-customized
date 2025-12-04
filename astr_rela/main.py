"""
AstrBot 人际关系管理插件
主入口文件
"""
from astrbot.api.event import filter
from astrbot.api.star import Context, Star, register
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
from astrbot.core.star.filter.permission import PermissionType
from astrbot.core.star.filter.platform_adapter_type import PlatformAdapterType

from .config import ConfigManager
from .commands import CommandHandler
from .events import EventHandler
from .message_handler import MessageHandler


@register(
    "astrbot_plugin_relationship",
    "Zhalslar",
    "[仅aiocqhttp] 人际关系管理器",
    "v2.0.2",
    "https://github.com/Zhalslar/astrbot_plugin_relationship",
)
class Relationship(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        
        # 初始化各个模块
        self.config_mgr = ConfigManager(config, context)
        self.msg_handler = MessageHandler(self.config_mgr)
        self.cmd_handler = CommandHandler(self, self.config_mgr, self.msg_handler)
        self.event_handler = EventHandler(self, self.config_mgr, self.msg_handler)

    # ==================== 管理员命令 ====================
    
    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("群列表")
    async def show_groups_info(self, event: AiocqhttpMessageEvent):
        """管理员命令：查看机器人已加入的所有群聊信息"""
        async for result in self.cmd_handler.show_groups_info(event):
            yield result

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("好友列表")
    async def show_friends_info(self, event: AiocqhttpMessageEvent):
        """管理员命令：查看所有好友信息"""
        async for result in self.cmd_handler.show_friends_info(event):
            yield result

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("退群")
    async def set_group_leave(self, event: AiocqhttpMessageEvent, group_id: int | None = None):
        """管理员命令：让机器人退出指定群聊"""
        async for result in self.cmd_handler.set_group_leave(event, group_id):
            yield result

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("删了", alias={"删除好友"})
    async def delete_friend(self, event: AiocqhttpMessageEvent, input_id: int | None = None):
        """管理员命令：删除指定好友（可@或输入QQ号）"""
        async for result in self.cmd_handler.delete_friend(event, input_id):
            yield result

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("同意")
    async def agree(self, event: AiocqhttpMessageEvent, extra: str = ""):
        """管理员命令：同意好友申请或群邀请"""
        async for result in self.cmd_handler.agree(event, extra):
            yield result

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("拒绝")
    async def refuse(self, event: AiocqhttpMessageEvent, extra: str = ""):
        """管理员命令：拒绝好友申请或群邀请"""
        async for result in self.cmd_handler.refuse(event, extra):
            yield result

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("抽查")
    async def check_messages_handle(
        self,
        event: AiocqhttpMessageEvent,
        group_id: int | None = None,
        count: int = 20,
    ):
        """管理员命令：抽查指定群聊的消息"""
        async for result in self.cmd_handler.check_messages_handle(event, group_id, count):
            yield result

    # ==================== 事件监听 ====================
    
    @filter.platform_adapter_type(PlatformAdapterType.AIOCQHTTP)
    async def event_monitoring(self, event: AiocqhttpMessageEvent):
        """监听好友申请或群邀请"""
        await self.event_handler.event_monitoring(event)

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_notice(self, event: AiocqhttpMessageEvent):
        """监听群聊相关事件（如管理员变动、禁言、踢出、邀请等），自动处理并反馈"""
        async for result in self.event_handler.on_notice(event):
            yield result
