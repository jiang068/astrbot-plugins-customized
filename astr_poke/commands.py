"""命令处理模块"""
import random
from astrbot.api.event import filter
from astrbot.api.message_components import At, Plain
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)


class PokeCommandHandler:
    """戳一戳命令处理器"""
    
    def __init__(self, config_manager, poke_executor):
        self.config = config_manager
        self.poke_executor = poke_executor
    
    async def handle_poke_command(self, event: AiocqhttpMessageEvent):
        """处理戳命令：戳@某人/我"""
        target_ids = [
            str(seg.qq)
            for seg in event.get_messages()
            if isinstance(seg, At) and str(seg.qq) != event.get_self_id()
        ]

        parsed_msg = event.message_str.split()
        times = int(parsed_msg[-1]) if parsed_msg[-1].isdigit() else 1
        if not event.is_admin():
            times = min(self.config.conf["poke_max_times"], times)

        is_poke_me = "我" in event.message_str
        if is_poke_me:
            target_ids.append(event.get_sender_id())

        if not target_ids:
            result: dict = await event.bot.get_group_msg_history(
                group_id=int(event.get_group_id())
            )
            target_ids = [msg["sender"]["user_id"] for msg in result["messages"]]

        if not target_ids:
            return

        await self.poke_executor(event, target_ids, times)
        
        # 根据是否戳我，发送不同的回复文本
        if is_poke_me and self.config.poke_me_reply_list:
            # 戳我后的回复
            reply_text = random.choice(self.config.poke_me_reply_list)
            await event.send(MessageChain(chain=[Plain(reply_text)]))  # type: ignore
        elif not is_poke_me and self.config.poke_others_reply_list:
            # 戳别人后的回复
            reply_text = random.choice(self.config.poke_others_reply_list)
            await event.send(MessageChain(chain=[Plain(reply_text)]))  # type: ignore
        
        event.stop_event()
