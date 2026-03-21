"""睡眠/苏醒状态机管理器。

本模块提供符合 Neo-MoFox 标准架构的管理器模式实现：
- 模块级单例管理运行时状态
- 集成 UnifiedScheduler 进行周期调度
- 提供状态推进、持久化与快照功能
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, cast

from src.app.plugin_system.api import storage_api
from src.app.plugin_system.api.log_api import get_logger
from src.core.prompt import get_system_reminder_store
from src.kernel.scheduler import TriggerType, get_unified_scheduler

from sleep_wakeup_plugin.components.configs.config import Config
from sleep_wakeup_plugin.core.state_machine import (
    CharacterState,
    DrowsinessPhase,
    RuntimeState,
    SleepWakeupStateMachine,
)

logger = get_logger("sleep_wakeup_plugin.managers.runtime")

# 管理器单例实例
_manager_instance: SleepWakeupManager | None = None


def get_sleep_wakeup_manager() -> SleepWakeupManager:
    """获取睡眠/苏醒管理器单例。

    Returns:
        SleepWakeupManager: 管理器实例

    Raises:
        RuntimeError: 如果管理器尚未初始化
    """
    if _manager_instance is None:
        raise RuntimeError(
            "SleepWakeupManager 尚未初始化，请在插件加载时调用 initialize_sleep_wakeup_manager()"
        )
    return _manager_instance


def initialize_sleep_wakeup_manager(
    plugin_name: str,
    config: Config,
) -> SleepWakeupManager:
    """初始化睡眠/苏醒管理器单例。

    Args:
        plugin_name: 插件名称，用于存储键
        config: 插件配置对象

    Returns:
        SleepWakeupManager: 初始化后的管理器实例
    """
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = SleepWakeupManager(
            plugin_name=plugin_name,
            config=config,
        )
        logger.info("SleepWakeupManager 管理器已初始化")
    return _manager_instance


class SleepWakeupManager:
    """睡眠/苏醒状态机管理器。

    负责状态推进、持久化、调度管理和运行态快照。
    遵循 Neo-MoFox 标准管理器模式。

    Attributes:
        _plugin_name: 插件名称
        _config: 插件配置
        _state_machine: 状态机实例
        _runtime_state: 当前运行时状态
        _state_lock: 状态操作异步锁
        _schedule_task_id: 调度任务 ID
    """

    # 睡眠报告在 system_reminder 中的存储位置
    _REMINDER_BUCKET = "actor"
    _REMINDER_NAME = "sleep_report"

    def __init__(
        self,
        *,
        plugin_name: str,
        config: Config,
    ) -> None:
        """初始化管理器。

        Args:
            plugin_name: 插件名称
            config: 插件配置对象
        """
        self._plugin_name = plugin_name
        self._config = config
        self._state_machine = self._build_state_machine(config)
        self._runtime_state: RuntimeState = RuntimeState()
        self._state_lock = asyncio.Lock()
        self._schedule_task_id: str | None = None

    async def initialize(self) -> None:
        """初始化管理器运行时。

        执行流程：
        1. 加载持久化状态
        2. 执行启动推进
        3. 启动周期调度任务

        Raises:
            Exception: 初始化过程中的任何异常
        """
        logger.info("SleepWakeupManager 开始初始化运行时")
        await self.load_runtime_state()
        await self.tick(source="startup")
        await self._start_scheduler()
        logger.info("SleepWakeupManager 运行时初始化完成")

    async def shutdown(self) -> None:
        """关闭管理器并清理资源。

        执行流程：
        1. 停止调度任务
        2. 持久化当前状态
        """
        logger.info("SleepWakeupManager 开始关闭")
        await self._stop_scheduler()
        await self.save_runtime_state()
        logger.info("SleepWakeupManager 已关闭")

    async def tick(self, source: str) -> list[str]:
        """推进一次状态机并在状态变化时持久化。

        Args:
            source: 触发来源标识（如 "scheduler"、"startup"）

        Returns:
            list[str]: 本次推进产生的事件列表
        """
        async with self._state_lock:
            before = self._runtime_state.to_dict()
            before_drowsiness = before.get("drowsiness", 0)
            before_state = before.get("character_state", "awake")

            now = datetime.now()
            self._runtime_state, events = await self._state_machine.tick(
                state=self._runtime_state,
                now=now,
                source=source,
            )
            self._trim_history()

            after = self._runtime_state.to_dict()
            after_drowsiness = after.get("drowsiness", 0)
            after_state = after.get("character_state", "awake")

            # 记录困倦值变化
            if before_drowsiness != after_drowsiness:
                delta = after_drowsiness - before_drowsiness
                logger.info(
                    f"困倦值变化: {before_drowsiness} -> {after_drowsiness} "
                    f"(delta={delta:+d}, source={source})"
                )

            # 记录状态转换
            if before_state != after_state:
                logger.info(f"角色状态转换: {before_state} -> {after_state}")
                if after_state == CharacterState.SLEEPING.value:
                    logger.info(f"角色进入睡眠状态 (困倦值达到 {after_drowsiness})")

            if self._config.general.debug_mode:
                logger.debug(
                    f"tick 执行完成: source={source}, drowsiness={after_drowsiness}, "
                    f"state={after_state}, events={events}"
                )

            # 持久化状态变更
            if before != after:
                await self.save_runtime_state()

            await self._handle_state_events(events)
            return events

    async def handle_private_message_wakeup(
        self,
        sender_id: str,
        platform: str,
    ) -> bool:
        """处理私聊消息触发的困倦值降低。

        根据配置调整困倦值，并在发生变化时记录日志。
        支持通过白名单/黑名单过滤用户。

        Args:
            sender_id: 发送者 ID
            platform: 平台标识（如 "qq"）

        Returns:
            bool: 是否发生了状态变更
        """
        if not self._config.guard.enable_private_message_wakeup:
            return False

        # 检查用户名单过滤
        if not self._check_user_in_wakeup_list(sender_id, platform):
            logger.debug(
                f"用户 {platform}:{sender_id} 不满足唤醒名单条件，跳过困倦值降低"
            )
            return False

        delta = max(0, self._config.guard.private_message_wakeup_delta)
        if delta <= 0:
            return False

        async with self._state_lock:
            before = self._runtime_state.to_dict()
            before_drowsiness = before.get("drowsiness", 0)

            now = datetime.now()
            (
                self._runtime_state,
                events,
            ) = await self._state_machine.apply_external_adjustment(
                self._runtime_state,
                delta=-delta,
                now=now,
                source="private_message",
                note=f"private_message_wakeup:-{delta}",
            )
            self._trim_history()

            after = self._runtime_state.to_dict()
            after_drowsiness = after.get("drowsiness", 0)

            changed = before != after
            if changed:
                await self.save_runtime_state()
                logger.info(
                    f"私聊消息触发唤醒调整: drowsiness {before_drowsiness} -> {after_drowsiness} "
                    f"(delta={-delta})"
                )

            await self._handle_state_events(events)
            return changed

    def _check_user_in_wakeup_list(
        self,
        sender_id: str,
        platform: str,
    ) -> bool:
        """检查用户是否满足唤醒名单条件。

        Args:
            sender_id: 发送者 ID
            platform: 平台标识

        Returns:
            bool: True 表示满足条件，False 表示不满足
        """
        list_type = self._config.guard.wakeup_user_list_type
        user_list = self._config.guard.wakeup_user_list

        # all 模式：允许所有用户
        if list_type == "all":
            return True

        # 构造用户标识符：platform:user_id
        user_key = f"{platform}:{sender_id}"

        # 标准化名单中的用户标识符（确保都是字符串）
        normalized_list = [str(item) for item in user_list]

        # whitelist 模式：只允许名单中的用户
        if list_type == "whitelist":
            if not normalized_list:  # 名单为空时，默认拒绝所有
                logger.debug(
                    f"白名单模式但名单为空，拒绝用户 {user_key}"
                )
                return False
            return user_key in normalized_list

        # blacklist 模式：拒绝名单中的用户
        if list_type == "blacklist":
            if not normalized_list:  # 名单为空时，默认允许所有
                return True
            return user_key not in normalized_list

        # 未知模式，默认允许
        logger.warning(
            f"未知的唤醒名单模式 '{list_type}'，默认允许用户 {user_key}"
        )
        return True

    async def load_runtime_state(self) -> None:
        """从 JSON 存储加载运行状态。

        如果检测到跨天旧状态，将自动清理并使用默认状态。

        Raises:
            Exception: 加载过程中的非致命异常会被捕获并记录
        """
        raw = await storage_api.load_json(
            self._plugin_name, self._config.storage.state_key
        )
        if not raw:
            self._runtime_state = RuntimeState()
            logger.info("未检测到历史状态，使用默认初始状态")
            return

        try:
            loaded_state = RuntimeState.from_dict(raw)
            purge, reason = await self._should_purge_stale_state(loaded_state)
            if purge:
                await storage_api.delete_json(
                    self._plugin_name, self._config.storage.state_key
                )
                self._runtime_state = RuntimeState()
                logger.info(f"已清理旧持久化状态: reason={reason}")
                return

            self._runtime_state = loaded_state
            self._trim_history()
            logger.info("已从 JSON 存储恢复运行状态")
        except Exception as exc:
            logger.warning(f"恢复状态失败，将使用默认状态: {exc}")
            self._runtime_state = RuntimeState()

    async def save_runtime_state(self) -> None:
        """保存运行状态到 JSON 存储。"""
        payload = self._runtime_state.to_dict()
        await storage_api.save_json(
            self._plugin_name,
            self._config.storage.state_key,
            cast(dict[str, Any], payload),
        )

    def get_runtime_snapshot(self) -> dict[str, Any]:
        """获取当前状态快照。

        Returns:
            dict: 状态快照字典
        """
        return self._runtime_state.to_dict()

    def should_block_messages(self) -> bool:
        """根据配置与当前状态判断是否需要阻挡消息。

        Returns:
            bool: True 表示应阻挡消息，False 表示放行
        """
        if not self._config.general.enabled:
            return False
        if not self._config.guard.block_messages_when_sleeping:
            return False
        return self._runtime_state.character_state == CharacterState.SLEEPING

    async def _start_scheduler(self) -> None:
        """启动周期调度任务。"""
        if self._schedule_task_id is not None:
            logger.warning("周期任务已存在，跳过启动")
            return

        scheduler = get_unified_scheduler()
        self._schedule_task_id = await scheduler.create_schedule(
            callback=self._scheduled_tick,
            trigger_type=TriggerType.TIME,
            trigger_config={
                "delay_seconds": self._config.timing.update_interval_seconds,
                "interval_seconds": self._config.timing.update_interval_seconds,
            },
            is_recurring=True,
            task_name=f"{self._plugin_name}:drowsiness_tick",
            timeout=60.0,
            max_retries=3,
        )
        logger.info(
            f"周期调度任务已启动: task_id={self._schedule_task_id}, "
            f"interval={self._config.timing.update_interval_seconds}s"
        )

    async def _stop_scheduler(self) -> None:
        """停止周期调度任务。"""
        if self._schedule_task_id is None:
            return

        scheduler = get_unified_scheduler()
        task_id = self._schedule_task_id
        self._schedule_task_id = None

        try:
            await scheduler.remove_schedule(task_id)
            logger.info(f"周期调度任务已移除: task_id={task_id}")
        except Exception as exc:
            logger.warning(f"移除周期任务失败: task_id={task_id}, error={exc}")

    async def _scheduled_tick(self) -> None:
        """周期调度任务回调。"""
        await self.tick(source="scheduler")

    def _trim_history(self) -> None:
        """按配置裁剪历史记录，保留最新的 N 条。"""
        limit = self._config.storage.max_history_records
        if len(self._runtime_state.history) > limit:
            self._runtime_state.history = self._runtime_state.history[-limit:]

    async def _should_purge_stale_state(self, state: RuntimeState) -> tuple[bool, str]:
        """判断是否应清理跨天旧状态。

        Args:
            state: 待检查的运行时状态

        Returns:
            tuple[bool, str]: (是否清理, 清理原因)
        """
        now = datetime.now()
        today = now.date().isoformat()
        state_date = state.record_date

        # 尝试从 last_updated_at 提取日期
        if not state_date and state.last_updated_at:
            try:
                state_date = (
                    datetime.fromisoformat(state.last_updated_at).date().isoformat()
                )
            except ValueError:
                state_date = None

        if not state_date:
            return False, "no_state_date"

        if state_date == today:
            pass  # 同一天，继续检查阶段

        current_phase = self._state_machine.resolve_phase(now)
        in_sleep_period = current_phase in {
            DrowsinessPhase.SLEEP,
            DrowsinessPhase.PRE_WAKE,
        }

        # 日期不匹配，清理
        if state_date != today:
            return True, "date_mismatch"

        # 非睡眠期，清理
        if not in_sleep_period:
            return True, f"not_in_sleep_period:{current_phase.value}"

        return False, "keep"

    async def _handle_state_events(self, events: list[str]) -> None:
        """处理状态切换事件：记录日志 + 注入/清理睡眠报告。

        Args:
            events: 事件列表
        """
        for event in events:
            if event == "switch_to_sleeping":
                logger.info("状态事件: 切换为 sleeping")
                await self._clear_sleep_report()
            elif event == "guardian_approved":
                logger.info("状态事件: guardian 批准苏醒，切换为 awake")
                await self._inject_sleep_report()
            elif event == "guardian_rejected":
                logger.info("状态事件: guardian 驳回苏醒，保持 sleeping")

    def _format_sleep_report(self, report: dict[str, Any]) -> str:
        """格式化睡眠报告为可读文本。

        Args:
            report: 睡眠报告字典

        Returns:
            str: 格式化后的报告文本
        """
        wake_time = report.get("wake_time", "未知时间")
        reason = report.get("reason", "未知原因")
        lie_in_count = report.get("lie_in_count", 0)
        guardian_trigger_count = report.get("guardian_trigger_count", 0)

        # 解析唤醒时间
        try:
            dt = datetime.fromisoformat(wake_time)
            wake_time_str = dt.strftime("%Y年%m月%d日 %H:%M")
        except (ValueError, TypeError):
            wake_time_str = str(wake_time)

        # 构建报告文本
        lines = [
            f"你刚刚苏醒过来（{wake_time_str}）。",
            f"苏醒原因：{reason}",
        ]

        if lie_in_count > 0:
            lines.append(f"赖床次数：{lie_in_count}")

        if guardian_trigger_count > 0:
            lines.append(f"守护检查次数：{guardian_trigger_count}")

        lines.append(
            "\n注：这是你的睡眠记录，你可以根据自己的情况自然地回应或忽略此信息。"
        )

        return "\n".join(lines)

    async def _inject_sleep_report(self) -> None:
        """将最近的睡眠报告注入到 system reminder 的 actor bucket。"""
        report = self._runtime_state.last_sleep_report
        if not report:
            logger.debug("无睡眠报告，跳过注入")
            return

        formatted = self._format_sleep_report(report)
        store = get_system_reminder_store()
        store.set(
            bucket=self._REMINDER_BUCKET,
            name=self._REMINDER_NAME,
            content=formatted,
        )
        logger.info(
            f"睡眠报告已注入到 system_reminder (bucket={self._REMINDER_BUCKET})"
        )

    async def _clear_sleep_report(self) -> None:
        """清理 system reminder 中的睡眠报告。"""
        store = get_system_reminder_store()
        deleted = store.delete(
            bucket=self._REMINDER_BUCKET,
            name=self._REMINDER_NAME,
        )
        if deleted:
            logger.info(
                f"已清理 system_reminder 中的睡眠报告 (bucket={self._REMINDER_BUCKET})"
            )
        else:
            logger.debug("未找到需要清理的睡眠报告")

    @staticmethod
    def _build_state_machine(config: Config) -> SleepWakeupStateMachine:
        """根据配置构建状态机实例。

        Args:
            config: 插件配置对象

        Returns:
            SleepWakeupStateMachine: 构建好的状态机实例
        """
        timing = config.timing
        model = config.model
        return SleepWakeupStateMachine(
            sleep_target_time=timing.sleep_target_time,
            wake_target_time=timing.wake_target_time,
            sleep_window_minutes=timing.sleep_window_minutes,
            wake_window_minutes=timing.wake_window_minutes,
            pre_sleep_step=model.pre_sleep_step,
            sleep_phase_step=model.sleep_phase_step,
            pre_wake_step=model.pre_wake_step,
            lie_in_reset_drowsiness=model.lie_in_reset_drowsiness,
            max_lie_in_attempts=model.max_lie_in_attempts,
            guardian_model_task=model.guardian_model_task,
            guardian_timeout_seconds=model.guardian_timeout_seconds,
        )
