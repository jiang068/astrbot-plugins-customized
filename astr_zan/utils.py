"""
工具函数模块
"""
import astrbot.api.message_components as Comp
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)


def get_ats(event: AiocqhttpMessageEvent) -> list[str]:
    """
    获取被at者们的id列表
    
    :param event: 消息事件对象
    :return: 被@的用户ID列表
    """
    messages = event.get_messages()
    self_id = event.get_self_id()
    return [
        str(seg.qq)
        for seg in messages
        if (isinstance(seg, Comp.At) and str(seg.qq) != self_id)
    ]
