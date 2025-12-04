"""
消息处理模块
处理消息发送和消息抽查功能
"""
from aiocqhttp import CQHttp
from astrbot import logger


class MessageHandler:
    """消息处理器"""

    def __init__(self, config_manager):
        self.config = config_manager

    async def send_reply(self, client: CQHttp, message: str):
        """发送回复消息到管理群或管理员私聊"""

        async def send_to_admins():
            """向所有管理员发送私聊消息"""
            for admin_id in self.config.admins_id:
                if admin_id.isdigit():
                    try:
                        await client.send_private_msg(
                            user_id=int(admin_id), message=message
                        )
                    except Exception as e:
                        logger.error(f"无法反馈管理员：{e}")

        if self.config.manage_group:
            try:
                await client.send_group_msg(
                    group_id=int(self.config.manage_group), message=message
                )
            except Exception as e:
                logger.error(f"无法反馈管理群：{e}")
                await send_to_admins()
        elif self.config.admins_id:
            await send_to_admins()

    async def check_messages(
        self,
        client: CQHttp,
        group_id: int | str = 0,
        user_id: int | str = 0,
        count: int = 20,
        reply_group_id: int | str = 0,
        reply_user_id: int | str = 0,
    ) -> bool:
        """抽查消息"""
        result = None
        if group_id:
            result = await client.get_group_msg_history(
                group_id=int(group_id), count=count
            )
        elif user_id:
            result = await client.get_friend_msg_history(
                user_id=int(user_id), count=count
            )

        if not result:
            return False

        messages: list[dict] = result.get("messages", [])

        if not messages:
            return False

        # 构造转发节点
        nodes = []
        for message in messages:
            node = {
                "type": "node",
                "data": {
                    "name": message["sender"]["nickname"],
                    "uin": message["sender"]["user_id"],
                    "content": message["message"],
                },
            }
            nodes.append(node)

        # 按优先级转发到目标
        if reply_group_id:
            await client.send_group_forward_msg(
                group_id=int(reply_group_id), messages=nodes
            )
        elif reply_user_id:
            await client.send_private_forward_msg(
                user_id=int(reply_user_id), messages=nodes
            )
        elif self.config.manage_group:
            await client.send_group_forward_msg(
                group_id=int(self.config.manage_group), messages=nodes
            )
        elif self.config.admins_id:
            for admin_id in self.config.admins_id:
                if admin_id.isdigit():
                    await client.send_private_forward_msg(
                        user_id=int(admin_id), messages=nodes
                    )
        return True
