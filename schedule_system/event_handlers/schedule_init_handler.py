"""定时任务初始化事件处理器

负责在插件加载完成后注册日程生成和月度计划生成的定时任务。
"""

from typing import TYPE_CHECKING

from src.core.components.base.event_handler import BaseEventHandler
from src.core.components.types import EventType
from src.kernel.event import EventDecision
from src.kernel.scheduler import get_unified_scheduler, TriggerType
from src.kernel.logger import get_logger

from ..managers.schedule_manager import get_schedule_manager
from ..utils.time_utils import get_tomorrow_str, get_today_str

if TYPE_CHECKING:
    from ..plugin import ScheduleSystemPlugin

logger = get_logger("schedule_system.schedule_init_handler", display="任务初始化")


class ScheduleInitHandler(BaseEventHandler):
    """定时任务初始化事件处理器

    负责在插件加载完成后注册日程生成和月度计划生成的定时任务。
    """

    handler_name: str = "schedule_init"
    handler_description: str = "初始化日程表定时任务"
    weight: int = 10
    intercept_message: bool = False
    init_subscribe: list[EventType | str] = [EventType.ON_START]

    def __init__(self, plugin: "ScheduleSystemPlugin"):
        super().__init__(plugin)
        self.plugin = plugin
        self._task_ids: list[str] = []  # 保存任务ID用于清理

    async def execute(
        self, event_name: str, params: dict
    ) -> tuple[EventDecision, dict]:
        """执行事件处理

        Args:
            event_name: 事件名称
            params: 事件参数

        Returns:
            (决策, 参数)
        """
        logger.info(f"收到事件: {event_name}, 开始注册定时任务")

        try:
            # 注册定时任务
            await self._register_scheduled_tasks()

            # 确保今日日程和本月计划
            await self._ensure_initial_data()

            logger.info("定时任务注册成功")

        except Exception as e:
            logger.error(f"定时任务注册失败: {e}", exc_info=True)

        return EventDecision.SUCCESS, params

    async def _register_scheduled_tasks(self) -> None:
        """注册定时任务到 UnifiedScheduler"""
        scheduler = get_unified_scheduler()

        # 注册每日日程生成任务
        if self.plugin.config.schedule.enabled:
            generation_time = self.plugin.config.schedule.generation_time  # "23:00"

            task_id = await scheduler.create_schedule(
                callback=self._generate_tomorrow_schedule,
                trigger_type=TriggerType.TIME,
                trigger_config={
                    "trigger_at": generation_time,
                    "interval_seconds": 86400,  # 24小时
                },
                is_recurring=True,
                task_name="schedule_system:daily_schedule_generation",
                timeout=300.0,
                max_retries=3,
            )

            self._task_ids.append(task_id)
            logger.info(
                f"日程生成任务已注册: task_id={task_id}, time={generation_time}"
            )

    async def _generate_tomorrow_schedule(self) -> None:
        """生成明日日程（定时任务回调）"""
        try:
            tomorrow = get_tomorrow_str()
            logger.info(f"开始生成明日日程: {tomorrow}")

            success = await get_schedule_manager().generate_for_date(tomorrow)

            if success:
                logger.info(f"明日日程生成成功: {tomorrow}")
            else:
                logger.warning(f"明日日程生成失败: {tomorrow}")

        except Exception as e:
            logger.error(f"明日日程生成异常: {e}", exc_info=True)

    async def _ensure_initial_data(self) -> None:
        """确保初始数据存在（今日日程）"""
        try:
            # 确保今日日程
            if self.plugin.config.schedule.enabled:
                today = get_today_str()
                manager = get_schedule_manager()

                # 检查今日日程是否存在
                schedule = await manager.get_schedule(today)
                if not schedule:
                    logger.info(f"今日 ({today}) 没有日程，开始生成")
                    await manager.generate_for_date(today)
                else:
                    logger.debug(f"今日 ({today}) 已有日程")

        except Exception as e:
            logger.error(f"确保初始数据失败: {e}", exc_info=True)

    async def cleanup(self) -> None:
        """清理：移除所有注册的定时任务"""
        logger.info("开始清理定时任务")

        try:
            scheduler = get_unified_scheduler()

            for task_id in self._task_ids:
                try:
                    await scheduler.remove_schedule(task_id)
                    logger.debug(f"移除任务: {task_id}")
                except Exception as e:
                    logger.warning(f"移除任务失败: task_id={task_id}, error={e}")

            self._task_ids.clear()
            logger.info("定时任务清理完成")

        except Exception as e:
            logger.error(f"清理任务失败: {e}", exc_info=True)
