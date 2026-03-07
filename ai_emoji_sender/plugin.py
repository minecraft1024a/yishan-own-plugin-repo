"""AI 表情包选择器插件

智能表情包选择功能：
- 从数据库随机抽取最多 50 个表情包
- 让 AI 根据聊天场景分析并选择最合适的表情包
- 自动发送选中的表情包
"""

from src.app.plugin_system.api.log_api import get_logger
from src.core.components.base import BasePlugin
from src.core.components.loader import register_plugin

from .components.actions.ai_emoji_selector import AIEmojiSelectorAction
from .components.configs.config import Config

logger = get_logger("ai_emoji_selector")


@register_plugin
class AIEmojiSelectorPlugin(BasePlugin):
    """AI 表情包选择器插件
    
    提供智能表情包选择功能。当 AI 认为需要发送表情包时，
    会从表情包库中随机抽取候选项，然后由 AI 分析场景选择最合适的表情包发送。
    """

    plugin_name = "ai_emoji_sender"
    plugin_version = "1.0.0"
    plugin_author = "MoFox Team"
    plugin_description = "AI 智能表情包选择器"
    configs = [Config]  # 注册配置组件

    def get_components(self) -> list[type]:
        """获取插件内所有组件类

        Returns:
            list[type]: 插件内所有组件类的列表
        """
        return [AIEmojiSelectorAction]
