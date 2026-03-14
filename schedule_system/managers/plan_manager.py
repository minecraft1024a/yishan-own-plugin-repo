"""月度计划管理器

负责月度计划的核心业务逻辑。
"""

from datetime import datetime
from typing import Any, Optional, TYPE_CHECKING

from src.kernel.logger import get_logger

if TYPE_CHECKING:
    from ..database import ScheduleDatabase
from ..utils.validation import validate_month, validate_priority

logger = get_logger("schedule_system.plan_manager", display="计划管理器")

_plan_manager_instance: Optional["PlanManager"] = None


def get_plan_manager() -> "PlanManager":
    """获取月度计划管理器单例

    Returns:
        PlanManager 实例

    Raises:
        RuntimeError: 如果管理器尚未初始化
    """
    if _plan_manager_instance is None:
        raise RuntimeError("PlanManager 尚未初始化，请先调用 initialize_plan_manager()")
    return _plan_manager_instance


def initialize_plan_manager(plugin: Any, db: "ScheduleDatabase") -> "PlanManager":
    """初始化并返回月度计划管理器单例

    Args:
        plugin: 插件实例
        db: 数据库访问层实例

    Returns:
        PlanManager 实例
    """
    global _plan_manager_instance
    if _plan_manager_instance is None:
        _plan_manager_instance = PlanManager(plugin, db)
        logger.info("PlanManager 单例已初始化")
    return _plan_manager_instance


class PlanManager:
    """月度计划管理器

    管理月度计划的 CRUD 操作和业务逻辑。
    """

    def __init__(self, plugin: Any, db: "ScheduleDatabase"):
        """初始化管理器

        Args:
            plugin: 插件实例
            db: 数据库访问层实例
        """
        self.plugin = plugin
        self.config = plugin.config
        self.db = db

    async def get_active_plans(self, month: str) -> list[dict[str, Any]]:
        """获取指定月份的活跃计划

        Args:
            month: 月份字符串 (YYYY-MM)

        Returns:
            计划列表
        """
        is_valid, error = validate_month(month)
        if not is_valid:
            logger.warning(f"月份验证失败: {error}")
            return []

        try:
            plans = await self.db.get_active_plans(month)
            return [plan.to_dict() for plan in plans]

        except Exception as e:
            logger.error(f"获取月度计划失败: {e}", exc_info=True)
            return []

    async def add_plan(
        self,
        month: str,
        plan_text: str,
        priority: int = 3,
        deadline: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> int:
        """添加月度计划

        Args:
            month: 目标月份
            plan_text: 计划内容
            priority: 优先级 (1-5)
            deadline: 截止日期 (可选)
            tags: 标签列表

        Returns:
            新建计划的 ID

        Raises:
            ValueError: 如果验证失败
        """
        # 验证
        is_valid, error = validate_month(month)
        if not is_valid:
            raise ValueError(f"月份验证失败: {error}")

        is_valid, error = validate_priority(priority)
        if not is_valid:
            raise ValueError(f"优先级验证失败: {error}")

        if not plan_text or len(plan_text) > 500:
            raise ValueError("计划内容必须在 1-500 个字符之间")

        try:
            plan_data = {
                "target_month": month,
                "plan_text": plan_text,
                "priority": priority,
                "deadline": deadline,
                "tags": tags or [],
                "status": "active",
                "auto_complete_threshold": self.config.plan.completion_threshold,
                "usage_count": 0,
            }
            plan = await self.db.create_plan(plan_data)

            logger.info(f"添加月度计划成功: id={plan.id}, month={month}")
            return plan.id

        except Exception as e:
            logger.error(f"添加月度计划失败: {e}", exc_info=True)
            raise

    async def complete_plan(self, plan_id: int) -> bool:
        """手动标记计划为已完成

        Args:
            plan_id: 计划 ID

        Returns:
            是否成功
        """
        try:
            updates = {
                "status": "completed",
                "completed_at": datetime.now(),
                "updated_at": datetime.now(),
            }
            success = await self.db.update_plan(plan_id, updates)

            if success:
                logger.info(f"标记计划为已完成: id={plan_id}")
            return success

        except Exception as e:
            logger.error(f"完成计划失败: {e}", exc_info=True)
            return False

    async def cancel_plan(self, plan_id: int) -> bool:
        """取消计划

        Args:
            plan_id: 计划 ID

        Returns:
            是否成功
        """
        try:
            updates = {
                "status": "cancelled",
                "updated_at": datetime.now(),
            }
            success = await self.db.update_plan(plan_id, updates)

            if success:
                logger.info(f"取消计划: id={plan_id}")
            return success

        except Exception as e:
            logger.error(f"取消计划失败: {e}", exc_info=True)
            return False

    async def update_plan(self, plan_id: int, **updates: Any) -> bool:
        """更新计划

        Args:
            plan_id: 计划 ID
            **updates: 要更新的字段

        Returns:
            是否成功
        """
        try:
            # 验证更新字段
            if "priority" in updates:
                is_valid, error = validate_priority(updates["priority"])
                if not is_valid:
                    raise ValueError(f"优先级验证失败: {error}")

            if "plan_text" in updates:
                if not updates["plan_text"] or len(updates["plan_text"]) > 500:
                    raise ValueError("计划内容必须在 1-500 个字符之间")

            updates["updated_at"] = datetime.now()
            success = await self.db.update_plan(plan_id, updates)

            if success:
                logger.info(f"更新计划成功: id={plan_id}")
            return success

        except Exception as e:
            logger.error(f"更新计划失败: {e}", exc_info=True)
            return False

    async def increment_usage(self, plan_id: int, used_date: str) -> bool:
        """增加计划使用次数

        Args:
            plan_id: 计划 ID
            used_date: 使用日期

        Returns:
            是否成功
        """
        try:
            # 获取当前计划
            plan = await self.db.get_plan_by_id(plan_id)
            if not plan:
                return False

            new_usage = plan.usage_count + 1
            updates = {
                "usage_count": new_usage,
                "last_used_date": used_date,
                "updated_at": datetime.now(),
            }

            # 检查是否达到自动完成阈值
            if new_usage >= plan.auto_complete_threshold:
                updates["status"] = "completed"
                updates["completed_at"] = datetime.now()
                logger.info(
                    f"计划达到自动完成阈值: id={plan_id}, usage={new_usage}"
                )

            await self.db.update_plan(plan_id, updates)
            return True

        except Exception as e:
            logger.error(f"增加使用次数失败: {e}", exc_info=True)
            return False
