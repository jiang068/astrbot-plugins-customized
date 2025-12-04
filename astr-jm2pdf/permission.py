"""权限管理模块

负责检查用户和群组的白名单权限
"""
from astrbot.api.event import AstrMessageEvent
from astrbot.api import logger


class PermissionChecker:
    """权限检查器"""
    
    def __init__(self, config_manager):
        """初始化权限检查器
        
        Args:
            config_manager: 配置管理器实例
        """
        self.config_manager = config_manager
    
    def check_whitelist(self, event: AstrMessageEvent) -> bool:
        """检查用户和群组是否在白名单中
        
        Args:
            event: 消息事件
            
        Returns:
            True表示允许使用，False表示拒绝
        """
        # 获取白名单配置
        whitelist_groups_str = self.config_manager.get_config_value('whitelist_groups', '')
        whitelist_users_str = self.config_manager.get_config_value('whitelist_users', '')
        
        # 解析白名单（去除空格，过滤空字符串）
        whitelist_groups = set()
        if whitelist_groups_str:
            whitelist_groups = {g.strip() for g in whitelist_groups_str.split(',') if g.strip()}
        
        whitelist_users = set()
        if whitelist_users_str:
            whitelist_users = {u.strip() for u in whitelist_users_str.split(',') if u.strip()}
        
        # 获取当前用户和群组信息
        user_id = str(event.get_sender_id())
        group_id = str(event.message_obj.group_id) if event.message_obj.group_id else ""
        is_group = bool(group_id)
        
        # 详细日志
        logger.info(f"白名单检查 - 用户ID: {user_id}, 群组ID: {group_id}, 是否群聊: {is_group}")
        logger.info(f"白名单用户配置: {whitelist_users if whitelist_users else '空(允许所有用户)'}")
        logger.info(f"白名单群组配置: {whitelist_groups if whitelist_groups else '空(允许所有群组)'}")
        
        # 新逻辑：用户白名单和群组白名单独立判断
        
        # 1. 检查用户白名单
        user_pass = False
        if not whitelist_users:
            # 用户白名单为空 = 允许所有用户
            user_pass = True
            logger.info(f"用户白名单未配置，用户 {user_id} 通过")
        elif user_id in whitelist_users:
            # 用户在白名单中
            user_pass = True
            logger.info(f"✅ 用户 {user_id} 在白名单中")
        else:
            logger.warning(f"❌ 用户 {user_id} 不在白名单中")
        
        # 2. 检查群组白名单（仅群聊时需要检查）
        group_pass = False
        if not is_group:
            # 私聊消息，不需要检查群组白名单
            group_pass = True
            logger.info("私聊消息，跳过群组白名单检查")
        elif not whitelist_groups:
            # 群组白名单为空 = 允许所有群组
            group_pass = True
            logger.info(f"群组白名单未配置，群组 {group_id} 通过")
        elif group_id in whitelist_groups:
            # 群组在白名单中
            group_pass = True
            logger.info(f"✅ 群组 {group_id} 在白名单中")
        else:
            logger.warning(f"❌ 群组 {group_id} 不在白名单中")
        
        # 3. 两者都需要通过（AND 逻辑）
        result = user_pass and group_pass
        
        if result:
            logger.info(f"✅ 白名单检查通过")
        else:
            logger.warning(f"❌ 白名单检查失败")
        
        return result
    
    def check_private_only(self, event: AstrMessageEvent) -> tuple[bool, str]:
        """检查是否开启了仅私聊模式，以及当前消息是否为群聊
        
        Args:
            event: 消息事件
            
        Returns:
            tuple[bool, str]: (是否应该拦截, 提示消息)
            - 如果返回 (True, message)，表示应该拦截并返回提示消息
            - 如果返回 (False, "")，表示可以继续执行
        """
        # 获取仅私聊配置
        private_only = self.config_manager.get_config_value('private_only', False)
        
        # 如果未开启仅私聊模式，直接通过
        if not private_only:
            return (False, "")
        
        # 检查当前消息是否为群聊
        group_id = str(event.message_obj.group_id) if event.message_obj.group_id else ""
        is_group = bool(group_id)
        
        if is_group:
            # 在群聊中触发，返回拦截和提示消息
            tip_message = self.config_manager.get_config_value('private_only_group_message', '全部私聊功能已开启！')
            logger.info(f"仅私聊模式已开启，拦截群聊 {group_id} 中的请求")
            return (True, tip_message)
        else:
            # 在私聊中触发，允许继续
            logger.info("仅私聊模式已开启，当前为私聊消息，允许继续")
            return (False, "")
