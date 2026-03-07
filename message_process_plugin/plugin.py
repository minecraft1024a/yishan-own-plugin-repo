"""
message_process_plugin 插件主类
"""

from src.app.plugin_system.api.log_api import get_logger
from src.core.components.base import BasePlugin
from src.core.components.loader import register_plugin

from message_process_plugin.components.configs.config import Config
from message_process_plugin.components.events.example_event import SegmentSenderEvent

logger = get_logger("message_process_plugin")


@register_plugin
class MessageProcessPluginPlugin(BasePlugin):
    """
    消息分段发送插件

    在消息发送前拦截，根据标点符号将文本消息分段，然后逐句发送。
    可用于长文本分段、模拟逐句输入效果等场景。
    """

    plugin_name = "message_process_plugin"
    plugin_version = "1.0.0"
    plugin_author = "minecraft1024a"
    plugin_description = "消息分段发送插件 - 根据标点符号分段逐句发送"
    configs = [Config]

    def get_components(self) -> list[type]:
        """获取插件内所有组件类

        Returns:
            list[type]: 插件内所有组件类的列表
        """
        return [SegmentSenderEvent]
