"""戳一戳响应处理器"""
import random
from astrbot.api.message_components import Face, Plain
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)


class PokeResponseHandler:
    """戳一戳响应处理器"""
    
    def __init__(self, config_manager, poke_executor):
        self.config = config_manager
        self.poke_executor = poke_executor
    
    async def poke_respond(self, event: AiocqhttpMessageEvent):
        """反戳"""
        await self.poke_executor(
            event=event,
            target_ids=event.get_sender_id(),
            times=random.randint(1, self.config.conf["poke_max_times"]),
        )
        
        # 如果配置了反戳后回复文本列表，则随机选择一条发送
        if self.config.poke_back_reply_list:
            reply_text = random.choice(self.config.poke_back_reply_list)
            await event.send(MessageChain(chain=[Plain(reply_text)]))  # type: ignore

    async def face_respond(self, event: AiocqhttpMessageEvent):
        """回复QQ表情"""
        if self.config.face_ids:
            face_id = random.choice(self.config.face_ids)
            face_count = random.randint(1, 3)
            faces_chain = [Face(id=face_id)] * face_count
            await event.send(MessageChain(chain=faces_chain))  # type: ignore

    async def text_respond(self, event: AiocqhttpMessageEvent):
        """回复预设文本"""
        if self.config.text_reply_list:
            reply_text = random.choice(self.config.text_reply_list)
            await event.send(MessageChain(chain=[Plain(reply_text)]))  # type: ignore
