"""
点赞处理模块
"""
import random
from aiocqhttp import CQHttp
import aiocqhttp
from .config import ConfigManager


class LikeHandler:
    """点赞处理器，负责处理点赞的核心逻辑"""
    
    def __init__(self, config_mgr: ConfigManager):
        self.config_mgr = config_mgr

    async def like(self, client: CQHttp, ids: list[str]) -> str:
        """
        点赞的核心逻辑
        
        :param client: CQHttp客户端
        :param ids: 用户ID列表
        :return: 点赞结果消息
        """
        replys = []
        for id in ids:
            total_likes = 0
            username = (await client.get_stranger_info(user_id=int(id))).get(
                "nickname", "未知用户"
            )
            for _ in range(5):
                try:
                    await client.send_like(user_id=int(id), times=10)  # 点赞10次
                    total_likes += 10
                except aiocqhttp.exceptions.ActionFailed as e:
                    error_message = str(e)
                    if "已达" in error_message:
                        error_reply = random.choice(self.config_mgr.limit_responses)
                    elif "权限" in error_message:
                        error_reply = random.choice(self.config_mgr.permission_responses)
                    else:
                        error_reply = random.choice(self.config_mgr.stranger_responses)
                    break

            reply = (
                random.choice(self.config_mgr.success_responses)
                if total_likes > 0
                else error_reply
            )

            # 检查 reply 中是否包含占位符，并根据需要进行替换
            if "{username}" in reply:
                reply = reply.replace("{username}", username)
            if "{total_likes}" in reply:
                reply = reply.replace("{total_likes}", str(total_likes))

            replys.append(reply)

        return "\n".join(replys).strip()
