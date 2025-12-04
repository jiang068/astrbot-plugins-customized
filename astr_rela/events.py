"""
事件处理模块
处理好友申请、群邀请、群通知等事件
"""
import asyncio
from astrbot import logger
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
from .utils import get_user_name, convert_duration_advanced


class EventHandler:
    """事件处理器"""

    def __init__(self, star_instance, config_manager, message_handler):
        self.star = star_instance
        self.config = config_manager
        self.msg_handler = message_handler

    async def event_monitoring(self, event: AiocqhttpMessageEvent):
        """监听好友申请或群邀请"""
        raw_message = getattr(event.message_obj, "raw_message", None)
        if (
            not isinstance(raw_message, dict)
            or raw_message.get("post_type") != "request"
        ):
            return

        logger.info(f"收到好友申请或群邀请: {raw_message}")
        client = event.bot
        user_id: int = raw_message.get("user_id", 0)
        nickname: str = (await client.get_stranger_info(user_id=int(user_id)))["nickname"] or "未知昵称"
        comment: str = raw_message.get("comment") or "无"
        flag = raw_message.get("flag")

        # 加好友事件
        if raw_message.get("request_type") == "friend":
            # 检查是否需要自动通过
            auto_approve = False
            if (
                self.config.enable_auto_approve 
                and self.config.auto_approve_keyword 
                and self.config.auto_approve_keyword in comment
            ):
                auto_approve = True
                try:
                    await client.set_friend_add_request(flag=flag, approve=True)
                    logger.info(f"自动通过好友申请：{nickname}({user_id})，验证信息：{comment}")
                    notice = (
                        f"【自动通过好友申请】\n"
                        f"昵称：{nickname}\n"
                        f"QQ号：{user_id}\n"
                        f"验证信息：{comment}\n"
                        f"匹配关键词：{self.config.auto_approve_keyword}"
                    )
                    await self.msg_handler.send_reply(client, notice)
                except Exception as e:
                    logger.error(f"自动通过好友申请失败：{e}")
                    notice = f"【收到好友申请】同意吗：\n昵称：{nickname}\nQQ号：{user_id}\nflag：{flag}\n验证信息：{comment}\n⚠️自动通过失败：{e}"
                    await self.msg_handler.send_reply(client, notice)
            else:
                # 功能未开启或关键词不匹配，走正常审批流程
                notice = f"【收到好友申请】同意吗：\n昵称：{nickname}\nQQ号：{user_id}\nflag：{flag}\n验证信息：{comment}"
                await self.msg_handler.send_reply(client, notice)

        # 群邀请事件
        elif (
            raw_message.get("request_type") == "group"
            and raw_message.get("sub_type") == "invite"
        ):
            group_id = raw_message.get("group_id", 0)
            group_name = (await client.get_group_info(group_id=group_id))["group_name"] or "未知群名"

            notice_to_admin = (
                f"【收到群邀请】同意吗\n"
                f"邀请人昵称：{nickname}\n"
                f"邀请人QQ：{user_id}\n"
                f"群名称：{group_name}\n"
                f"群号：{group_id}\n"
                f"flag：{flag}\n"
                f"验证信息：{comment}"
            )
            if self.config.is_group_in_blacklist(group_id):
                notice_to_admin += "\n❗警告: 该群为黑名单群聊，请谨慎通过，若通过则自动移出黑名单"

            reply_to_inviter = (
                "想加好友或拉群？要等审核们审批哟"
                if self.config.manage_group
                else "想加好友或拉群？要等审核审批哟"
            )
            if self.config.is_group_in_blacklist(group_id):
                reply_to_inviter += "\n⚠️该群已被列入黑名单，可能不会通过审核。"

            await self.msg_handler.send_reply(client, notice_to_admin)
            try:
                await client.send_private_msg(user_id=int(user_id), message=reply_to_inviter)
            except Exception as e:
                logger.error(f"无法向邀请者 {user_id} 发送提示: {e}")

    async def on_notice(self, event: AiocqhttpMessageEvent):
        """监听群聊相关事件（如管理员变动、禁言、踢出、邀请等），自动处理并反馈"""
        raw_message = getattr(event.message_obj, "raw_message", None)
        self_id = event.get_self_id()

        if (
            not raw_message
            or not isinstance(raw_message, dict)
            or raw_message.get("post_type") != "notice"
            or raw_message.get("user_id", 0) != int(self_id)
        ):
            return

        client = event.bot
        group_id = raw_message.get("group_id", 0)
        group_info = await client.get_group_info(group_id=group_id)
        group_name = group_info.get("group_name")
        operator_id = raw_message.get("operator_id", 0)
        
        if operator_id == int(self_id):
            return
            
        operator_name = await get_user_name(client, user_id=operator_id, group_id=group_id)

        # 群管理员变动
        if raw_message.get("notice_type") == "group_admin":
            if raw_message.get("sub_type") == "set":
                await self.msg_handler.send_reply(
                    client, f"哇！我成为了 {group_name}({group_id}) 的管理员"
                )
            else:
                await self.msg_handler.send_reply(
                    client, f"呜呜ww..我在 {group_name}({group_id}) 的管理员被撤了"
                )

            if self.config.auto_check_messages:
                await self.msg_handler.check_messages(client, group_id=group_id)
            event.stop_event()

        # 群禁言事件
        elif raw_message.get("notice_type") == "group_ban":
            duration = raw_message.get("duration", 0)
            if duration == 0:
                await self.msg_handler.send_reply(
                    client,
                    f"好耶！{operator_name} 在 {group_name}({group_id}) 解除了我的禁言",
                )
            else:
                await self.msg_handler.send_reply(
                    client,
                    f"呜呜ww..我在 {group_name}({group_id}) 被 {operator_name} 禁言了{convert_duration_advanced(duration)}",
                )
            
            if self.config.auto_check_messages:
                await self.msg_handler.check_messages(client, group_id=group_id)

            if duration > self.config.max_ban_duration:
                await self.msg_handler.send_reply(
                    client,
                    f"禁言时间超过{convert_duration_advanced(self.config.max_ban_duration)}，我退群了",
                )
                if self.config.auto_check_messages:
                    await self.msg_handler.check_messages(client, group_id=group_id)
                await asyncio.sleep(3)
                await client.set_group_leave(group_id=group_id)

            event.stop_event()

        # 群成员减少事件 (被踢)
        elif (
            raw_message.get("notice_type") == "group_decrease"
            and raw_message.get("sub_type") == "kick_me"
        ):
            if not self.config.is_group_in_blacklist(group_id):
                self.config.add_to_blacklist(group_id)
                logger.info(f"群聊 {group_id} 已因被踢被加入黑名单。")

            reply = f"呜呜ww..我被 {operator_name} 踢出了 {group_name}({group_id})，已将此群拉进黑名单"
            await self.msg_handler.send_reply(client, reply)

            if self.config.auto_check_messages:
                await self.msg_handler.check_messages(client, group_id=group_id)
            event.stop_event()

        # 群成员增加事件 (被邀请)
        elif (
            raw_message.get("notice_type") == "group_increase"
            and raw_message.get("sub_type") == "invite"
        ):
            delay_str = convert_duration_advanced(self.config.new_group_check_delay)
            await self.msg_handler.send_reply(
                client,
                f"主人..我被 {operator_name} 拉进了 {group_name}({group_id})。\n"
                f"我将在{delay_str}后抽查该群消息",
            )

            # 获取当前群列表
            group_list = await client.get_group_list()

            # 互斥成员检查
            mutual_blacklist_set = set(self.config.mutual_blacklist.copy())
            mutual_blacklist_set.discard(self_id)
            member_list = await client.get_group_member_list(group_id=group_id)
            member_ids: list[str] = [str(member["user_id"]) for member in member_list]
            common_ids: set[str] = set(member_ids) & mutual_blacklist_set

            # 检查1：如果群在黑名单里，则退群
            if self.config.is_group_in_blacklist(group_id):
                await self.msg_handler.send_reply(
                    client, f"群聊 {group_name}({group_id}) 在黑名单里，我退群了"
                )
                yield event.plain_result("把我踢了还想要我回来？退了退了")
                await asyncio.sleep(3)
                await client.set_group_leave(group_id=group_id)

            # 检查2：如果群总数超过最大容量，则退群
            elif len(group_list) > self.config.max_group_capacity:
                await self.msg_handler.send_reply(
                    client,
                    f"我已经加了{len(group_list)}个群（超过了{self.config.max_group_capacity}个），这群我退了",
                )
                yield event.plain_result(
                    f"我最多只能加{self.config.max_group_capacity}个群，现在已经加了{len(group_list)}个群，请不要拉我进群了"
                )
                await asyncio.sleep(3)
                await client.set_group_leave(group_id=group_id)

            # 检查3：如果群内存在互斥成员，则退群
            elif common_ids:
                user_id = common_ids.pop()
                member_name = await get_user_name(
                    client, user_id=int(user_id), group_id=group_id
                )
                await self.msg_handler.send_reply(
                    client,
                    f"检测到群内存在互斥成员 {member_name}({user_id})，这群我退了",
                )
                yield event.plain_result(f"我不想和{member_name}({user_id})在同一个群里，退了")
                await asyncio.sleep(3)
                await client.set_group_leave(group_id=group_id)

            if self.config.auto_check_messages:
                await asyncio.sleep(self.config.new_group_check_delay)
                await self.msg_handler.check_messages(client, group_id=group_id)

            event.stop_event()
