"""日程表服务

对外暴露日程表管理的标准接口，供其他插件调用。
"""

from typing import Any, Optional, TYPE_CHECKING

from src.core.components.base.service import BaseService
from src.kernel.logger import get_logger

from ..managers.schedule_manager import get_schedule_manager
from ..utils.time_utils import get_today_str

if TYPE_CHECKING:
    from ..plugin import ScheduleSystemPlugin

logger = get_logger("schedule_system.schedule_service", display="日程服务")


class ScheduleService(BaseService):
    """日程表服务

    对外暴露日程表管理的标准接口，供其他插件调用。
    """

    service_name: str = "schedule"
    service_description: str = "日程表管理服务"
    version: str = "2.0.0"

    dependencies: list[str] = []  # 可选：["memory_plugin:service:memory"]

    def __init__(self, plugin: "ScheduleSystemPlugin"):
        super().__init__(plugin)
        self.plugin = plugin

    @property
    def manager(self):
        """获取 ScheduleManager 单例"""
        return get_schedule_manager()

    # ==================== 公开 API ====================

    async def get_schedule(self, date: str) -> list[dict[str, Any]]:
        """获取指定日期的日程

        Args:
            date: 日期字符串 (YYYY-MM-DD)

        Returns:
            日程项列表，每项包含 id, time_range, activity, priority, tags 等字段

        Examples:
            >>> schedule = await service.get_schedule("2026-03-14")
            >>> for item in schedule:
            ...     print(f"{item['time_range']}: {item['activity']}")
        """
        return await self.manager.get_schedule(date)

    async def get_current_activity(self) -> Optional[dict[str, Any]]:
        """获取当前正在进行的活动

        Returns:
            当前活动信息，如果没有则返回 None

        Examples:
            >>> current = await service.get_current_activity()
            >>> if current:
            ...     print(f"当前活动: {current['activity']}")
        """
        return await self.manager.get_current_activity()

    async def add_schedule_item(
        self,
        date: str,
        time_range: str,
        activity: str,
        priority: int = 3,
        tags: Optional[list[str]] = None,
    ) -> int:
        """添加日程项

        Args:
            date: 日期 (YYYY-MM-DD)
            time_range: 时间范围 (HH:MM-HH:MM)
            activity: 活动描述
            priority: 优先级 (1-5)
            tags: 标签列表

        Returns:
            新建日程项的 ID

        Raises:
            ValueError: 如果参数验证失败

        Examples:
            >>> item_id = await service.add_schedule_item(
            ...     date="2026-03-14",
            ...     time_range="14:00-15:00",
            ...     activity="会议",
            ...     priority=4,
            ...     tags=["工作", "重要"]
            ... )
        """
        return await self.manager.add_item(date, time_range, activity, priority, tags or [])

    async def update_schedule_item(self, item_id: int, **updates: Any) -> bool:
        """更新日程项

        Args:
            item_id: 日程项 ID
            **updates: 要更新的字段 (time_range, activity, priority, tags, is_completed 等)

        Returns:
            是否成功

        Examples:
            >>> success = await service.update_schedule_item(
            ...     item_id=123,
            ...     activity="会议（延期）",
            ...     priority=5
            ... )
        """
        return await self.manager.update_item(item_id, **updates)

    async def delete_schedule_item(self, item_id: int) -> bool:
        """删除日程项

        Args:
            item_id: 日程项 ID

        Returns:
            是否成功

        Examples:
            >>> success = await service.delete_schedule_item(123)
        """
        return await self.manager.delete_item(item_id)

    async def regenerate_schedule(self, date: str) -> bool:
        """重新生成指定日期的日程

        会删除旧日程并使用 LLM 生成新的日程。

        Args:
            date: 日期字符串 (YYYY-MM-DD)

        Returns:
            是否成功

        Examples:
            >>> success = await service.regenerate_schedule("2026-03-15")
        """
        # 先标记旧日程为非活跃
        await self.manager.regenerate(date)

        # 然后生成新日程
        return await self.generate_schedule_for_date(date)

    async def ensure_today_schedule(self) -> None:
        """确保今日日程存在（启动时调用）

        如果今日没有日程，则自动生成。
        """
        today = get_today_str()
        schedule = await self.manager.get_schedule(today)

        if not schedule:
            logger.info(f"今日 ({today}) 没有日程，开始生成")
            await self.generate_schedule_for_date(today)
        else:
            logger.debug(f"今日 ({today}) 已有日程")

    async def generate_schedule_for_date(self, date: str) -> bool:
        """为指定日期生成日程

        Args:
            date: 日期字符串 (YYYY-MM-DD)

        Returns:
            是否成功

        Examples:
            >>> success = await service.generate_schedule_for_date("2026-03-16")
        """
        return await self.manager.generate_for_date(date)

    async def get_generation_status(self) -> dict[str, Any]:
        """查询当前生成状态

        Returns:
            状态信息字典，包含:
            - generation_in_progress: 是否正在生成
            - config: 相关配置信息

        Examples:
            >>> status = await service.get_generation_status()
            >>> if status["generation_in_progress"]:
            ...     print("正在生成日程...")
        """
        return await self.manager.get_status()
