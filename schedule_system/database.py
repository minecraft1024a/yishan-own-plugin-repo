"""数据库访问层

封装所有数据库操作，使用 PluginDatabase 独立存储。
"""

from typing import Any, Optional

from src.app.plugin_system.api.storage_api import PluginDatabase
from src.kernel.logger import get_logger

from .models import Schedule, ScheduleItem, MonthlyPlan, ActivityStatistics

logger = get_logger("schedule_system.database", display="数据库访问")

_db_instance: Optional["ScheduleDatabase"] = None


def get_schedule_database(db_path: str = "data/schedule_system/schedule.db") -> "ScheduleDatabase":
    """获取日程数据库单例

    Args:
        db_path: 数据库文件路径，仅首次创建时生效

    Returns:
        ScheduleDatabase 实例
    """
    global _db_instance
    if _db_instance is None:
        _db_instance = ScheduleDatabase(db_path)
    return _db_instance


class ScheduleDatabase:
    """日程系统数据库访问层

    封装所有数据库操作，统一管理。
    """

    def __init__(self, db_path: str = "data/schedule_system/schedule.db"):
        """初始化数据库

        Args:
            db_path: 数据库文件路径
        """
        self.db = PluginDatabase(
            db_path=db_path,
            models=[Schedule, ScheduleItem, MonthlyPlan, ActivityStatistics],
        )
        self._initialized = False

    async def initialize(self) -> None:
        """初始化数据库（创建表）"""
        if not self._initialized:
            await self.db.initialize()
            self._initialized = True
            logger.info("数据库初始化完成")

    async def close(self) -> None:
        """关闭数据库连接"""
        await self.db.close()
        self._initialized = False
        logger.info("数据库连接已关闭")

    # ==================== Schedule 操作 ====================

    async def get_schedule_by_date(
        self, date: str, is_active: bool = True
    ) -> Optional[Schedule]:
        """根据日期获取日程表

        Args:
            date: 日期字符串 (YYYY-MM-DD)
            is_active: 是否只获取活跃的日程

        Returns:
            Schedule 对象或 None
        """
        try:
            result = await self.db.query(Schedule).filter(
                date=date, is_active=is_active
            ).first()
            return result
        except Exception as e:
            logger.error(f"查询日程失败: {e}", exc_info=True)
            return None

    async def create_schedule(self, schedule_data: dict[str, Any]) -> Optional[Schedule]:
        """创建日程表

        Args:
            schedule_data: 日程表数据

        Returns:
            创建的 Schedule 对象或 None
        """
        try:
            return await self.db.crud(Schedule).create(schedule_data)
        except Exception as e:
            logger.error(f"创建日程失败: {e}", exc_info=True)
            return None

    async def update_schedule(
        self, schedule_id: int, updates: dict[str, Any]
    ) -> bool:
        """更新日程表

        Args:
            schedule_id: 日程表 ID
            updates: 更新数据

        Returns:
            是否成功
        """
        try:
            await self.db.crud(Schedule).update(schedule_id, updates)
            return True
        except Exception as e:
            logger.error(f"更新日程失败: {e}", exc_info=True)
            return False

    # ==================== ScheduleItem 操作 ====================

    async def get_schedule_items(
        self, schedule_id: int
    ) -> list[ScheduleItem]:
        """获取日程表的所有日程项

        Args:
            schedule_id: 日程表 ID

        Returns:
            ScheduleItem 对象列表
        """
        try:
            return await self.db.query(ScheduleItem).filter(
                schedule_id=schedule_id
            ).all()
        except Exception as e:
            logger.error(f"查询日程项失败: {e}", exc_info=True)
            return []

    async def get_schedule_item_by_id(
        self, item_id: int
    ) -> Optional[ScheduleItem]:
        """根据 ID 获取日程项

        Args:
            item_id: 日程项 ID

        Returns:
            ScheduleItem 对象或 None
        """
        try:
            return await self.db.crud(ScheduleItem).get(item_id)
        except Exception as e:
            logger.error(f"查询日程项失败: {e}", exc_info=True)
            return None

    async def create_schedule_item(
        self, item_data: dict[str, Any]
    ) -> Optional[ScheduleItem]:
        """创建日程项

        Args:
            item_data: 日程项数据

        Returns:
            创建的 ScheduleItem 对象或 None
        """
        try:
            return await self.db.crud(ScheduleItem).create(item_data)
        except Exception as e:
            logger.error(f"创建日程项失败: {e}", exc_info=True)
            return None

    async def update_schedule_item(
        self, item_id: int, updates: dict[str, Any]
    ) -> bool:
        """更新日程项

        Args:
            item_id: 日程项 ID
            updates: 更新数据

        Returns:
            是否成功
        """
        try:
            await self.db.crud(ScheduleItem).update(item_id, updates)
            return True
        except Exception as e:
            logger.error(f"更新日程项失败: {e}", exc_info=True)
            return False

    async def delete_schedule_item(self, item_id: int) -> bool:
        """删除日程项

        Args:
            item_id: 日程项 ID

        Returns:
            是否成功
        """
        try:
            await self.db.crud(ScheduleItem).delete(item_id)
            return True
        except Exception as e:
            logger.error(f"删除日程项失败: {e}", exc_info=True)
            return False

    # ==================== MonthlyPlan 操作 ====================

    async def get_active_plans(self, month: str) -> list[MonthlyPlan]:
        """获取指定月份的活跃计划

        Args:
            month: 月份字符串 (YYYY-MM)

        Returns:
            MonthlyPlan 对象列表
        """
        try:
            return await self.db.query(MonthlyPlan).filter(
                target_month=month, status="active"
            ).all()
        except Exception as e:
            logger.error(f"查询月度计划失败: {e}", exc_info=True)
            return []

    async def get_completed_plans(self, month: str) -> list[MonthlyPlan]:
        """获取指定月份的已完成计划

        Args:
            month: 月份字符串 (YYYY-MM)

        Returns:
            MonthlyPlan 对象列表
        """
        try:
            return await self.db.query(MonthlyPlan).filter(
                target_month=month, status="completed"
            ).limit(5).all()
        except Exception as e:
            logger.error(f"查询已完成计划失败: {e}", exc_info=True)
            return []

    async def get_plan_by_id(self, plan_id: int) -> Optional[MonthlyPlan]:
        """根据 ID 获取计划

        Args:
            plan_id: 计划 ID

        Returns:
            MonthlyPlan 对象或 None
        """
        try:
            return await self.db.crud(MonthlyPlan).get(plan_id)
        except Exception as e:
            logger.error(f"查询计划失败: {e}", exc_info=True)
            return None

    async def create_plan(self, plan_data: dict[str, Any]) -> Optional[MonthlyPlan]:
        """创建月度计划

        Args:
            plan_data: 计划数据

        Returns:
            创建的 MonthlyPlan 对象或 None
        """
        try:
            return await self.db.crud(MonthlyPlan).create(plan_data)
        except Exception as e:
            logger.error(f"创建计划失败: {e}", exc_info=True)
            return None

    async def update_plan(self, plan_id: int, updates: dict[str, Any]) -> bool:
        """更新计划

        Args:
            plan_id: 计划 ID
            updates: 更新数据

        Returns:
            是否成功
        """
        try:
            await self.db.crud(MonthlyPlan).update(plan_id, updates)
            return True
        except Exception as e:
            logger.error(f"更新计划失败: {e}", exc_info=True)
            return False

    # ==================== ActivityStatistics 操作 ====================

    async def get_statistics(
        self, activity_type: str
    ) -> Optional[ActivityStatistics]:
        """获取活动统计

        Args:
            activity_type: 活动类型

        Returns:
            ActivityStatistics 对象或 None
        """
        try:
            return await self.db.query(ActivityStatistics).filter(
                activity_type=activity_type
            ).first()
        except Exception as e:
            logger.error(f"查询统计失败: {e}", exc_info=True)
            return None

    async def create_or_update_statistics(
        self, activity_type: str, updates: dict[str, Any]
    ) -> bool:
        """创建或更新活动统计

        Args:
            activity_type: 活动类型
            updates: 统计数据

        Returns:
            是否成功
        """
        try:
            existing = await self.get_statistics(activity_type)

            if existing:
                await self.db.crud(ActivityStatistics).update(existing.id, updates)
            else:
                updates["activity_type"] = activity_type
                await self.db.crud(ActivityStatistics).create(updates)

            return True
        except Exception as e:
            logger.error(f"更新统计失败: {e}", exc_info=True)
            return False
