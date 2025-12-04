"""工具函数模块"""
import asyncio
from astrbot.api import logger
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)


async def execute_poke(
    event: AiocqhttpMessageEvent,
    target_ids: list | str,
    times: int,
    poke_interval: float,
):
    """
    执行戳一戳操作
    
    Args:
        event: 消息事件
        target_ids: 目标用户ID列表
        times: 戳的次数
        poke_interval: 戳的间隔时间
    """
    client = event.bot
    group_id = event.get_group_id()
    self_id = int(event.get_self_id())
    
    if isinstance(target_ids, str | int):
        target_ids = [target_ids]
    
    target_ids = list(
        dict.fromkeys(  # 保留顺序去重
            int(tid) for tid in target_ids if int(tid) != self_id
        )
    )

    async def poke_func(tid: int):
        if group_id:
            await client.group_poke(group_id=int(group_id), user_id=tid)
        else:
            await client.friend_poke(user_id=tid)

    try:
        for tid in target_ids:
            for _ in range(times):
                await poke_func(tid)
                await asyncio.sleep(poke_interval)
    except Exception as e:
        logger.error(f"执行戳一戳失败：{e}")
