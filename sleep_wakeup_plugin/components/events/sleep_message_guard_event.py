"""睡眠期消息拦截事件处理器。

本模块提供睡眠状态下的消息拦截功能。
遵循 Neo-MoFox 标准架构，通过管理器单例访问运行时状态。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.app.plugin_system.api.log_api import get_logger
from src.core.components.base import BaseEventHandler
from src.core.components.types import EventType
from src.kernel.event import EventDecision

from sleep_wakeup_plugin.managers import get_sleep_wakeup_manager

if TYPE_CHECKING:
    from sleep_wakeup_plugin.plugin import SleepWakeupPlugin

logger = get_logger("sleep_wakeup_plugin.events.guard")

# 聊天类型常量
PRIVATE_CHAT = "private"


class SleepMessageGuardEvent(BaseEventHandler):
    """在睡眠状态阻挡消息事件的守护处理器。

    该事件处理器负责：
    1. 检测私聊消息并触发唤醒调整
    2. 在睡眠状态时阻挡消息事件
    3. 遵循"访问父插件仅限配置"的原则

    Attributes:
        handler_name: 处理器唯一标识符
        handler_description: 处理器功能描述
        weight: 事件优先级（1000 为高优先级，早于其他处理器执行）
        intercept_message: 允许拦截消息事件
        init_subscribe: 订阅的事件类型列表
    """

    handler_name = "sleep_message_guard_event"
    handler_description = "睡眠期阻挡消息事件"
    weight = 1000  # 高优先级，在其他处理器之前执行
    intercept_message = True
    init_subscribe = [
        EventType.ON_MESSAGE_RECEIVED,
        EventType.ON_RECEIVED_OTHER_MESSAGE,
        EventType.ON_MESSAGE_SENT,
    ]

    def __init__(self, plugin: "SleepWakeupPlugin") -> None:
        """初始化事件处理器。

        Args:
            plugin: 父插件实例（仅用于配置访问）
        """
        super().__init__(plugin)
        self.plugin = plugin

    async def execute(
        self,
        event_name: str,
        params: dict[str, Any],
    ) -> tuple[EventDecision, dict[str, Any]]:
        """根据插件状态决定是否拦截消息。

        处理流程：
        1. 检测是否为接收侧私聊消息
        2. 如果是私聊消息，触发唤醒调整（通过管理器）
        3. 检查当前是否应阻挡消息
        4. 返回 STOP（阻挡）或 SUCCESS（放行）

        Args:
            event_name: 事件名称
            params: 事件参数字典

        Returns:
            tuple[EventDecision, dict]: 事件处理决策和参数
        """
        # 检测私聊消息并触发唤醒调整
        if self._is_incoming_private_message(event_name, params):
            try:
                # 提取发送者和平台信息
                message = params.get("message")
                if message is None:
                    logger.warning("私聊消息事件缺少 message 对象")
                    return EventDecision.SUCCESS, params

                # 直接访问 Message 对象的属性
                sender_id = message.sender_id or ""
                platform = message.platform or ""

                # 验证必要字段
                if not sender_id or not platform:
                    logger.debug(
                        f"私聊消息缺少必要字段: sender_id={sender_id}, platform={platform}"
                    )
                    return EventDecision.SUCCESS, params

                # 调用管理器处理唤醒（传递用户信息）
                manager = get_sleep_wakeup_manager()
                changed = await manager.handle_private_message_wakeup(
                    sender_id=sender_id,
                    platform=platform,
                )
                if changed:
                    logger.debug(
                        f"私聊消息触发唤醒调整: event={event_name}, "
                        f"user={platform}:{sender_id}"
                    )
            except RuntimeError:
                logger.warning("管理器未初始化，无法处理私聊唤醒")

        # 检查是否应阻挡消息
        try:
            manager = get_sleep_wakeup_manager()
            should_block = manager.should_block_messages()
        except RuntimeError:
            should_block = False  # 管理器未初始化，默认不阻挡

        if should_block:
            logger.debug(f"睡眠守护已拦截事件: {event_name}")
            return EventDecision.STOP, params

        return EventDecision.SUCCESS, params

    @staticmethod
    def _is_incoming_private_message(
        event_name: str,
        params: dict[str, Any],
    ) -> bool:
        """判断是否为接收侧私聊消息事件。

        检测逻辑：
        1. 事件类型必须是 ON_MESSAGE_RECEIVED
        2. 聊天类型必须是 "private"

        Args:
            event_name: 事件名称
            params: 事件参数字典

        Returns:
            bool: True 表示是私聊消息，False 表示不是
        """
        # 检查事件类型
        if event_name != EventType.ON_MESSAGE_RECEIVED.value:
            return False

        # 尝试从 message 对象获取聊天类型
        message = params.get("message")
        chat_type = str(getattr(message, "chat_type", "")).lower()

        # 如果 message 对象没有 chat_type，尝试从 params 直接获取
        if not chat_type:
            chat_type = str(params.get("chat_type", "")).lower()

        return chat_type == PRIVATE_CHAT
