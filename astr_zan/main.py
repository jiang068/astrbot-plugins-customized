"""
AstrBot 点赞插件
主入口文件
"""
from astrbot.api.event import filter
from astrbot.api.star import Context, Star, register
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)
from astrbot.core.star.filter.permission import PermissionType

from .config import ConfigManager
from .like_handler import LikeHandler
from .utils import get_ats


@register(
    "astr_zan",
    "Futureppo",
    "发送 赞我 自动点赞",
    "1.0.8",
    "https://github.com/Futureppo/astrbot_plugin_zanwo",
)
class zanwo(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        
        # 初始化各个模块
        self.config_mgr = ConfigManager(config)
        self.like_handler = LikeHandler(self.config_mgr)

    @filter.regex(r"^赞.*")
    async def like_me(self, event: AiocqhttpMessageEvent):
        """给用户点赞"""
        # 检查群组id是否在白名单中, 若没填写白名单则不检查
        if self.config_mgr.enable_white_list_groups:
            if event.get_group_id() not in self.config_mgr.white_list_groups:
                return
        
        target_ids = []
        if event.message_str == "赞我":
            target_ids.append(event.get_sender_id())
        if not target_ids:
            target_ids = get_ats(event)
        if not target_ids:
            return
        
        client = event.bot
        result = await self.like_handler.like(client, target_ids)
        yield event.plain_result(result)

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("谁赞了bot", alias={"谁赞了你"})
    async def get_profile_like(self, event: AiocqhttpMessageEvent):
        """获取bot自身点赞列表"""
        client = event.bot
        data = await client.get_profile_like()
        reply = ""
        user_infos = data.get("favoriteInfo", {}).get("userInfos", [])
        for user in user_infos:
            if (
                "nick" in user
                and user["nick"]
                and "count" in user
                and user["count"] > 0
            ):
                reply += f"\n【{user['nick']}】赞了我{user['count']}次"
        if not reply:
            reply = "暂无有效的点赞信息"
        url = await self.text_to_image(reply)
        yield event.image_result(url)

