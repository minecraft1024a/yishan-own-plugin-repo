"""睡眠/苏醒插件管理器模块。"""

from __future__ import annotations

from .sleep_wakeup_manager import (
    SleepWakeupManager,
    get_sleep_wakeup_manager,
    initialize_sleep_wakeup_manager,
)

__all__ = [
    "SleepWakeupManager",
    "get_sleep_wakeup_manager",
    "initialize_sleep_wakeup_manager",
]
