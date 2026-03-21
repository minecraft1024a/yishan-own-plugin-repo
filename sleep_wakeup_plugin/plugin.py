"""sleep_wakeup_plugin 插件主类。

本插件实现离散睡眠/苏醒状态机，支持守护决策与消息阻挡。
采用标准管理器模式，通过模块级单例管理运行时状态。
"""

from __future__ import annotations

from typing import Any

from src.app.plugin_system.api.log_api import get_logger
from src.core.components.base import BasePlugin
from src.core.components.loader import register_plugin

from sleep_wakeup_plugin.components.configs.config import Config
from sleep_wakeup_plugin.components.events.sleep_message_guard_event import (
    SleepMessageGuardEvent,
)
from sleep_wakeup_plugin.components.events.startup_event import SleepWakeupStartupEvent
from sleep_wakeup_plugin.managers import (
    get_sleep_wakeup_manager,
    initialize_sleep_wakeup_manager,
)

logger = get_logger("sleep_wakeup_plugin")


@register_plugin
class SleepWakeupPlugin(BasePlugin):
    """LLM 睡眠/苏醒状态机插件。

    本插件提供离散睡眠/苏醒状态机功能：
    - 根据时间自动调整困倦值
    - 守护 Agent 决策是否苏醒
    - 睡眠期间可选阻挡消息
    - 私聊消息可触发唤醒

    Attributes:
        plugin_name: 插件唯一标识符
        plugin_version: 插件版本号
        plugin_author: 插件作者
        plugin_description: 插件功能描述
        configs: 配置组件列表
    """

    plugin_name = "sleep_wakeup_plugin"
    plugin_version = "1.0.0"
    plugin_author = "minecraft1024a"
    plugin_description = "离散睡眠/苏醒状态机，支持守护决策与消息阻挡"
    configs = [Config]

    def __init__(self, config: Config | None = None) -> None:
        """初始化插件实例。

        Args:
            config: 插件配置对象，若为 None 则使用默认配置
        """
        super().__init__(config)
        self.config: Config = config or Config()

    def get_components(self) -> list[type]:
        """返回插件组件列表。

        Returns:
            list[type]: 包含配置和事件处理器的组件列表
        """
        return [Config, SleepWakeupStartupEvent, SleepMessageGuardEvent]

    async def on_plugin_loaded(self) -> None:
        """插件加载钩子：初始化管理器单例。

        执行流程：
        1. 检查插件是否启用
        2. 调用 initialize_sleep_wakeup_manager() 创建管理器单例
        3. 等待 ON_START 事件触发运行时初始化
        """
        logger.info("sleep_wakeup_plugin 加载开始")

        if not self.config.general.enabled:
            logger.warning("插件已禁用，跳过状态机初始化")
            return

        initialize_sleep_wakeup_manager(
            plugin_name=self.plugin_name,
            config=self.config,
        )

        logger.info("sleep_wakeup_plugin 装配完成，等待 ON_START 初始化")

    async def on_plugin_unloaded(self) -> None:
        """插件卸载钩子：关闭管理器并清理资源。

        执行流程：
        1. 停止周期调度任务
        2. 持久化当前状态
        3. 释放管理器资源
        """
        logger.info("sleep_wakeup_plugin 卸载中")

        try:
            manager = get_sleep_wakeup_manager()
            await manager.shutdown()
        except RuntimeError:
            logger.warning("管理器未初始化，跳过关闭流程")

        logger.info("sleep_wakeup_plugin 卸载完成")

    def should_block_messages(self) -> bool:
        """返回当前是否应阻挡消息事件。

        这是一个便捷方法，内部调用管理器的同名方法。
        主要供外部插件或组件快速查询阻挡状态。

        Returns:
            bool: True 表示应阻挡消息，False 表示放行

        Note:
            如果管理器未初始化，返回 False（不阻挡）
        """
        try:
            manager = get_sleep_wakeup_manager()
            return manager.should_block_messages()
        except RuntimeError:
            return False

    def get_runtime_snapshot(self) -> dict[str, Any]:
        """获取当前状态快照。

        这是一个便捷方法，内部调用管理器的同名方法。
        主要供调试或监控使用。

        Returns:
            dict[str, Any]: 状态快照字典，包含困倦值、角色状态等信息

        Note:
            如果管理器未初始化，返回空字典
        """
        try:
            manager = get_sleep_wakeup_manager()
            return manager.get_runtime_snapshot()
        except RuntimeError:
            return {}
