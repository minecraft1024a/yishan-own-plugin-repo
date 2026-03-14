"""日程管理器

负责日程表的核心业务逻辑。
"""

import asyncio
from datetime import datetime
from typing import Any, Optional, TYPE_CHECKING

from src.kernel.logger import get_logger
from ..generators.schedule_generator import ScheduleGenerator

if TYPE_CHECKING:
    from ..database import ScheduleDatabase
    from ..plugin import ScheduleSystemPlugin
from ..utils.time_utils import get_current_time_str, is_time_in_range
from ..utils.validation import (
    validate_activity,
    validate_date,
    validate_priority,
    validate_time_range,
)

logger = get_logger("schedule_system.schedule_manager", display="日程管理器")

_schedule_manager_instance: Optional["ScheduleManager"] = None


def get_schedule_manager() -> "ScheduleManager":
    """获取日程管理器单例

    Returns:
        ScheduleManager 实例

    Raises:
        RuntimeError: 如果管理器尚未初始化
    """
    if _schedule_manager_instance is None:
        raise RuntimeError("ScheduleManager 尚未初始化，请先调用 initialize_schedule_manager()")
    return _schedule_manager_instance


def initialize_schedule_manager(plugin: "ScheduleSystemPlugin", db: "ScheduleDatabase") -> "ScheduleManager":
    """初始化并返回日程管理器单例

    Args:
        plugin: 插件实例
        db: 数据库访问层实例

    Returns:
        ScheduleManager 实例
    """
    global _schedule_manager_instance
    if _schedule_manager_instance is None:
        _schedule_manager_instance = ScheduleManager(plugin, db)
        logger.info("ScheduleManager 单例已初始化")
    return _schedule_manager_instance


class ScheduleManager:
    """日程管理器

    管理日程表的 CRUD 操作和业务逻辑。
    """

    def __init__(self, plugin: "ScheduleSystemPlugin", db: "ScheduleDatabase"):
        """初始化管理器

        Args:
            plugin: 插件实例
            db: 数据库访问层实例
        """
        self.plugin = plugin
        self.config = plugin.config
        self.db = db
        self._generator = ScheduleGenerator(plugin)
        self._generation_lock = asyncio.Lock()
        self._generation_in_progress = False

    async def get_schedule(self, date: str) -> list[dict[str, Any]]:
        """获取指定日期的日程

        Args:
            date: 日期字符串 (YYYY-MM-DD)

        Returns:
            日程项列表
        """
        is_valid, error = validate_date(date)
        if not is_valid:
            logger.warning(f"日期验证失败: {error}")
            return []

        try:
            schedule = await self.db.get_schedule_by_date(date, is_active=True)
            if not schedule:
                logger.info(f"未找到日期 {date} 的日程")
                return []

            items = await self.db.get_schedule_items(schedule.id)
            return [item.to_dict() for item in items]

        except Exception as e:
            logger.error(f"获取日程失败: {e}", exc_info=True)
            return []

    async def get_current_activity(self) -> Optional[dict[str, Any]]:
        """获取当前正在进行的活动

        Returns:
            当前活动信息，如果没有则返回 None
        """
        from ..utils.time_utils import get_today_str

        today = get_today_str()
        current_time = get_current_time_str()

        try:
            schedule = await self.db.get_schedule_by_date(today, is_active=True)
            if not schedule:
                return None

            items = await self.db.get_schedule_items(schedule.id)

            for item in items:
                if is_time_in_range(current_time, item.time_range):
                    return item.to_dict()

            return None

        except Exception as e:
            logger.error(f"获取当前活动失败: {e}", exc_info=True)
            return None

    async def add_item(
        self,
        date: str,
        time_range: str,
        activity: str,
        priority: int = 3,
        tags: Optional[list[str]] = None,
    ) -> int:
        """添加日程项

        Args:
            date: 日期
            time_range: 时间范围
            activity: 活动描述
            priority: 优先级 (1-5)
            tags: 标签列表

        Returns:
            新建日程项的 ID

        Raises:
            ValueError: 如果验证失败
        """
        # 验证
        is_valid, error = validate_date(date)
        if not is_valid:
            raise ValueError(f"日期验证失败: {error}")

        is_valid, error = validate_time_range(time_range)
        if not is_valid:
            raise ValueError(f"时间范围验证失败: {error}")

        is_valid, error = validate_activity(activity)
        if not is_valid:
            raise ValueError(f"活动描述验证失败: {error}")

        is_valid, error = validate_priority(priority)
        if not is_valid:
            raise ValueError(f"优先级验证失败: {error}")

        try:
            # 确保日程表存在
            schedule = await self.db.get_schedule_by_date(date, is_active=True)
            if not schedule:
                schedule_data = {
                    "date": date,
                    "version": 1,
                    "is_active": True,
                    "generated_by": "manual",
                }
                schedule = await self.db.create_schedule(schedule_data)

            # 创建日程项
            item_data = {
                "schedule_id": schedule.id,
                "time_range": time_range,
                "activity": activity,
                "priority": priority,
                "tags": tags or [],
                "is_completed": False,
                "is_auto_generated": False,
            }
            item = await self.db.create_schedule_item(item_data)

            logger.info(
                f"添加日程项成功: id={item.id}, date={date}, activity={activity}"
            )
            return item.id

        except Exception as e:
            logger.error(f"添加日程项失败: {e}", exc_info=True)
            raise

    async def update_item(self, item_id: int, **updates: Any) -> bool:
        """更新日程项

        Args:
            item_id: 日程项 ID
            **updates: 要更新的字段

        Returns:
            是否成功
        """
        try:
            # 验证更新字段
            if "time_range" in updates:
                is_valid, error = validate_time_range(updates["time_range"])
                if not is_valid:
                    raise ValueError(f"时间范围验证失败: {error}")

            if "activity" in updates:
                is_valid, error = validate_activity(updates["activity"])
                if not is_valid:
                    raise ValueError(f"活动描述验证失败: {error}")

            if "priority" in updates:
                is_valid, error = validate_priority(updates["priority"])
                if not is_valid:
                    raise ValueError(f"优先级验证失败: {error}")

            # 更新
            updates["updated_at"] = datetime.now()
            await self.db.update_schedule_item(item_id, updates)

            logger.info(f"更新日程项成功: id={item_id}")
            return True

        except Exception as e:
            logger.error(f"更新日程项失败: {e}", exc_info=True)
            return False

    async def delete_item(self, item_id: int) -> bool:
        """删除日程项

        Args:
            item_id: 日程项 ID

        Returns:
            是否成功
        """
        try:
            success = await self.db.delete_schedule_item(item_id)
            if success:
                logger.info(f"删除日程项成功: id={item_id}")
            return success

        except Exception as e:
            logger.error(f"删除日程项失败: {e}", exc_info=True)
            return False

    async def regenerate(self, date: str) -> bool:
        """重新生成指定日期的日程

        Args:
            date: 日期字符串

        Returns:
            是否成功
        """
        try:
            # 删除旧日程
            old_schedule = await self.db.get_schedule_by_date(date, is_active=True)
            if old_schedule:
                await self.db.update_schedule(old_schedule.id, {"is_active": False})

            # 生成新日程（需要通过 generator）
            # 这里返回 True，实际生成由 service 层调用 generator
            logger.info(f"标记旧日程为非活跃: date={date}")
            return True

        except Exception as e:
            logger.error(f"重新生成日程失败: {e}", exc_info=True)
            return False

    async def generate_for_date(self, date: str) -> bool:
        """为指定日期生成日程

        Args:
            date: 日期字符串

        Returns:
            是否成功
        """
        async with self._generation_lock:
            if self._generation_in_progress:
                logger.warning("日程生成已在进行中，跳过")
                return False

            self._generation_in_progress = True
            try:
                # 调用内置生成器
                result = await self._generator.generate(date)

                if result:
                    logger.info(f"日程生成成功: date={date}")
                    return True
                else:
                    logger.warning(f"日程生成失败: date={date}")
                    return False

            finally:
                self._generation_in_progress = False

    async def get_status(self) -> dict[str, Any]:
        """获取生成状态

        Returns:
            状态信息
        """
        return {
            "generation_in_progress": self._generation_in_progress,
            "config": {
                "enabled": self.config.schedule.enabled,
                "max_retries": self.config.schedule.max_retries,
                "generation_model": self.config.schedule.generation_model,
            },
        }
