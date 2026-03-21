"""睡眠插件启动初始化事件处理器。

本模块提供系统启动时的初始化事件处理器。
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

logger = get_logger("sleep_wakeup_plugin.events.startup")


class SleepWakeupStartupEvent(BaseEventHandler):
    """在 ON_START 时初始化运行时与调度。

    该事件处理器在系统启动时被触发，负责：
    1. 调用管理器的 initialize() 方法
    2. 加载持久化状态
    3. 启动周期调度任务

    Attributes:
        handler_name: 处理器唯一标识符
        handler_description: 处理器功能描述
        weight: 事件优先级（数值越大越优先）
        intercept_message: 是否拦截消息事件
        init_subscribe: 订阅的事件类型列表
    """

    handler_name = "sleep_wakeup_startup_event"
    handler_description = "系统启动时初始化 sleep_wakeup_plugin 调度"
    weight = 100
    intercept_message = False
    init_subscribe = [EventType.ON_START]

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
        """处理系统启动事件。

        通过管理器单例执行初始化流程。

        Args:
            event_name: 事件名称
            params: 事件参数字典

        Returns:
            tuple[EventDecision, dict]: 事件处理结果和参数
        """
        try:
            manager = get_sleep_wakeup_manager()
            await manager.initialize()
            logger.info("sleep_wakeup_plugin 启动初始化成功")
        except RuntimeError as exc:
            logger.error(f"管理器未初始化，无法启动: {exc}", exc_info=True)
        except Exception as exc:
            logger.error(f"ON_START 初始化失败: {exc}", exc_info=True)

        return EventDecision.SUCCESS, params
