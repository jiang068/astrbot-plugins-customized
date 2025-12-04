"""AstrBot 戳一戳插件"""
import random
import time

from astrbot.api import logger
from astrbot.api.event import filter
from astrbot.api.message_components import Poke
from astrbot.api.star import Context, Star, register
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.config.default import VERSION
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)
from astrbot.core.utils.version_comparator import VersionComparator

from .config import ConfigManager
from .handlers import PokeResponseHandler
from .commands import PokeCommandHandler
from .utils import execute_poke


@register("astr_poke", "", "戳一戳插件", "1.0.0")
class PokeproPlugin(Star):
    """戳一戳插件"""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        
        # 检查版本
        if not VersionComparator.compare_version(VERSION, "4.5.7") >= 0:
            raise Exception("AstrBot 版本过低, 请升级至 4.5.7 或更高版本")
        
        # 初始化配置管理器
        self.config_manager = ConfigManager(config)
        
        # 记录每个 user_id 的最后触发时间
        self.last_trigger_time = {}
        
        # 创建戳一戳执行器（闭包，传递配置）
        async def poke_executor(event, target_ids, times):
            await execute_poke(
                event, 
                target_ids, 
                times, 
                self.config_manager.conf["poke_interval"]
            )
        
        # 初始化响应处理器
        self.response_handler = PokeResponseHandler(
            self.config_manager, 
            poke_executor
        )
        
        # 初始化命令处理器
        self.command_handler = PokeCommandHandler(
            self.config_manager, 
            poke_executor
        )

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_poke(self, event: AiocqhttpMessageEvent):
        """监听并响应戳一戳事件"""
        if event.get_extra("is_poke_event"):
            return
        raw_message = getattr(event.message_obj, "raw_message", None)

        if (
            not raw_message
            or not event.message_obj.message
            or not isinstance(event.message_obj.message[0], Poke)
        ):
            return

        target_id: int = raw_message.get("target_id", 0)
        user_id: int = raw_message.get("user_id", 0)
        self_id: int = raw_message.get("self_id", 0)
        group_id: int = raw_message.get("group_id", 0)

        # 冷却机制
        current_time = time.monotonic()
        last_time = self.last_trigger_time.get(user_id, 0)
        if current_time - last_time < self.config_manager.conf["cooldown_seconds"]:
            return
        self.last_trigger_time[user_id] = current_time

        # 过滤与自身无关的戳
        if target_id != self_id:
            # 跟戳机制
            if (
                group_id
                and user_id != self_id
                and random.random() < self.config_manager.conf["follow_poke_th"]
            ):
                await event.bot.group_poke(group_id=int(group_id), user_id=target_id)
            return

        # 根据独立概率触发响应（每种响应独立判断，可以同时触发多种）
        try:
            # 反戳
            poke_back_prob = self.config_manager.conf.get("poke_back_probability", 0.3)
            if random.random() < poke_back_prob:
                await self.response_handler.poke_respond(event)
            
            # 文本回复（与反戳完全独立）
            text_reply_prob = self.config_manager.conf.get("text_reply_probability", 0.6)
            if random.random() < text_reply_prob:
                await self.response_handler.text_respond(event)

            # 表情回复
            face_reply_prob = self.config_manager.conf.get("face_reply_probability", 0.5)
            if random.random() < face_reply_prob:
                await self.response_handler.face_respond(event)
                
        except Exception as e:
            logger.error(f"执行戳一戳响应失败: {e}", exc_info=True)

    @filter.command("戳", alias={"戳我"})
    async def poke_handle(self, event: AiocqhttpMessageEvent):
        """戳@某人/我"""
        await self.command_handler.handle_poke_command(event)
