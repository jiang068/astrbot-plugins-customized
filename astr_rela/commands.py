"""
命令处理模块
包含所有管理员命令的处理逻辑
"""
from astrbot import logger
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
from .utils import get_at_id, get_user_name, get_reply_text


class CommandHandler:
    """命令处理器"""

    def __init__(self, star_instance, config_manager, message_handler):
        self.star = star_instance
        self.config = config_manager
        self.msg_handler = message_handler

    async def show_groups_info(self, event: AiocqhttpMessageEvent):
        """管理员命令：查看机器人已加入的所有群聊信息"""
        client = event.bot
        group_list = await client.get_group_list()
        group_info = "\n\n".join(
            f"{i + 1}. {g['group_id']}: {g['group_name']}"
            for i, g in enumerate(group_list)
        )
        info = f"【群列表】共加入{len(group_list)}个群：\n\n{group_info}"
        url = await self.star.text_to_image(info)
        yield event.image_result(url)

    async def show_friends_info(self, event: AiocqhttpMessageEvent):
        """管理员命令：查看所有好友信息"""
        client = event.bot
        friend_list = await client.get_friend_list()
        friend_info = "\n\n".join(
            f"{i + 1}. {f['user_id']}: {f['nickname']}"
            for i, f in enumerate(friend_list)
        )
        info = f"【好友列表】共{len(friend_list)}位好友：\n\n{friend_info}"
        url = await self.star.text_to_image(info)
        yield event.image_result(url)

    async def set_group_leave(self, event: AiocqhttpMessageEvent, group_id: int | None = None):
        """管理员命令：让机器人退出指定群聊"""
        if not group_id:
            yield event.plain_result("要指明退哪个群哟~")
            return

        client = event.bot
        group_list = await client.get_group_list()
        group_ids = [int(group["group_id"]) for group in group_list]
        
        if group_id not in group_ids:
            yield event.plain_result("我没加有这个群")
            return

        await client.set_group_leave(group_id=group_id)
        yield event.plain_result(f"已退出群聊：{group_id}")

    async def delete_friend(self, event: AiocqhttpMessageEvent, input_id: int | None = None):
        """管理员命令：删除指定好友（可@或输入QQ号）"""
        target_id: int | None = get_at_id(event) or input_id
        if not target_id:
            yield event.plain_result("请 @ 要删除的好友或提供其QQ号。")
            return

        client = event.bot
        friend_list = await client.get_friend_list()
        friend_ids = [int(friend["user_id"]) for friend in friend_list]
        
        if target_id not in friend_ids:
            yield event.plain_result("我没加有这个人")
            return

        await client.delete_friend(user_id=target_id)
        yield event.plain_result(
            f"已删除好友：{await get_user_name(client=client, user_id=target_id)}({target_id})"
        )

    async def agree(self, event: AiocqhttpMessageEvent, extra: str = ""):
        """管理员命令：同意好友申请或群邀请"""
        reply = await self.approve(event=event, extra=extra, approve=True)
        if reply:
            yield event.plain_result(reply)

    async def refuse(self, event: AiocqhttpMessageEvent, extra: str = ""):
        """管理员命令：拒绝好友申请或群邀请"""
        reply = await self.approve(event=event, extra=extra, approve=False)
        if reply:
            yield event.plain_result(reply)

    async def approve(self, event: AiocqhttpMessageEvent, extra: str = "", approve: bool = True) -> str | None:
        """处理好友申请或群邀请的主函数"""
        text = get_reply_text(event)
        if not text:
            return "需引用一条好友申请或群邀请"
        
        lines = text.split("\n")
        client = event.bot

        # 处理好友申请
        if "【收到好友申请】" in text and len(lines) >= 5:
            nickname = lines[1].split("：")[1]
            uid = lines[2].split("：")[1]
            flag = lines[3].split("：")[1]
            
            friend_list = await client.get_friend_list()
            uids = [str(f["user_id"]) for f in friend_list]
            
            if uid in uids:
                return f"【{nickname}】已经是我的好友啦"

            try:
                await client.set_friend_add_request(
                    flag=flag, approve=approve, remark=extra
                )
                if not approve:
                    return f"已拒绝好友：{nickname}"
                return f"已同意好友：{nickname}" + (f"\n并备注为：{extra}" if extra else "")
            except:  # noqa: E722
                return "这条申请处理过了或者格式不对"

        # 处理群邀请
        elif "【收到群邀请】" in text and len(lines) >= 7:
            group_name = lines[3].split("：")[1]
            gid = lines[4].split("：")[1]
            flag = lines[5].split("：")[1]
            
            group_list = await client.get_group_list()
            gids = [str(f["group_id"]) for f in group_list]
            
            if gid in gids:
                return f"我已经在【{group_name}】里啦"

            try:
                if approve and gid in self.config.group_blacklist:
                    self.config.remove_from_blacklist(gid)
                    
                await client.set_group_add_request(
                    flag=flag, sub_type="invite", approve=approve, reason=extra
                )
                
                if approve:
                    return f"已同意群邀请: {group_name}"
                else:
                    return f"已拒绝群邀请: {group_name}" + (f"\n理由：{extra}" if extra else "")
            except:  # noqa: E722
                return "这条申请处理过了或者格式不对"

    async def check_messages_handle(
        self,
        event: AiocqhttpMessageEvent,
        group_id: int | None = None,
        count: int = 20,
    ):
        """抽查指定群聊的消息"""
        if not group_id:
            yield event.plain_result("未指定群号")
            return
        
        try:
            await self.msg_handler.check_messages(
                client=event.bot,
                group_id=group_id,
                reply_group_id=event.get_group_id(),
                reply_user_id=event.get_sender_id(),
                count=count,
            )
            event.stop_event()
        except Exception as e:
            logger.error(f"抽查群({group_id})消息失败: {e}")
            yield event.plain_result(f"抽查群({group_id})消息失败: {e}")
