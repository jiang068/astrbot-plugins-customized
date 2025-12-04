"""配置管理模块"""
import re
from astrbot.core.config.astrbot_config import AstrBotConfig


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config: AstrBotConfig):
        self.conf = config
        
        # 反戳后回复文本列表
        self.poke_back_reply_list: list[str] = self._string_to_list(
            config.get("poke_back_reply_list", ""), "str"
        )

        # 文本回复列表
        self.text_reply_list: list[str] = self._string_to_list(
            config.get("text_reply_list", ""), "str"
        )

        # 表情ID列表
        self.face_ids: list[int] = self._string_to_list(
            config.get("face_ids_str", ""), "int"
        )
        
        # 戳别人后的回复文本列表
        self.poke_others_reply_list: list[str] = self._string_to_list(
            config.get("poke_others_reply_list", ""), "str"
        )
        
        # 戳我后的回复文本列表
        self.poke_me_reply_list: list[str] = self._string_to_list(
            config.get("poke_me_reply_list", ""), "str"
        )

    @staticmethod
    def _string_to_list(
        input_str: str,
        return_type: str = "str",
        sep: str | list[str] = [":", "：", ",", "，"],
    ) -> list[str | int]:
        """
        将字符串转换为列表，支持自定义一个或多个分隔符和返回类型。

        参数：
            input_str (str): 输入字符串。
            return_type (str): 返回类型，'str' 或 'int'。
            sep (Union[str, List[str]]): 一个或多个分隔符，默认为 [":", "；", ",", "，"]。
        返回：
            List[Union[str, int]]
        """
        # 如果sep是列表，则创建一个包含所有分隔符的正则表达式模式
        if isinstance(sep, list):
            pattern = "|".join(map(re.escape, sep))
        else:
            # 如果sep是单个字符，则直接使用
            pattern = re.escape(sep)

        parts = [p.strip() for p in re.split(pattern, input_str) if p.strip()]

        if return_type == "int":
            try:
                return [int(p) for p in parts]
            except ValueError as e:
                raise ValueError(f"转换失败 - 无效的整数: {e}")
        elif return_type == "str":
            return parts
        else:
            raise ValueError("return_type 必须是 'str' 或 'int'")
