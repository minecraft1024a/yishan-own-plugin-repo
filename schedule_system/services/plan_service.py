"""月度计划服务

对外暴露月度计划管理的标准接口，供其他插件调用。
"""

from typing import Any, Optional, TYPE_CHECKING

from src.core.components.base.service import BaseService
from src.kernel.logger import get_logger

from ..managers.plan_manager import get_plan_manager

if TYPE_CHECKING:
    from ..plugin import ScheduleSystemPlugin

logger = get_logger("schedule_system.plan_service", display="计划服务")


class PlanService(BaseService):
    """月度计划服务

    对外暴露月度计划管理的标准接口，供其他插件调用。
    """

    service_name: str = "plan"
    service_description: str = "月度计划管理服务"
    version: str = "2.0.0"

    dependencies: list[str] = []

    def __init__(self, plugin: "ScheduleSystemPlugin"):
        super().__init__(plugin)
        self.plugin = plugin

    @property
    def manager(self):
        """获取 PlanManager 单例"""
        return get_plan_manager()

    # ==================== 公开 API ====================

    async def get_active_plans(self, month: str) -> list[dict[str, Any]]:
        """获取指定月份的活跃计划

        Args:
            month: 月份字符串 (YYYY-MM)

        Returns:
            计划列表，每项包含 id, plan_text, priority, status, usage_count 等字段

        Examples:
            >>> plans = await service.get_active_plans("2026-03")
            >>> for plan in plans:
            ...     print(f"{plan['plan_text']} (已使用 {plan['usage_count']} 次)")
        """
        return await self.manager.get_active_plans(month)

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
            month: 目标月份 (YYYY-MM)
            plan_text: 计划内容
            priority: 优先级 (1-5)
            deadline: 截止日期 (YYYY-MM-DD，可选)
            tags: 标签列表

        Returns:
            新建计划的 ID

        Raises:
            ValueError: 如果参数验证失败

        Examples:
            >>> plan_id = await service.add_plan(
            ...     month="2026-03",
            ...     plan_text="每周运动3次",
            ...     priority=4,
            ...     tags=["健康"]
            ... )
        """
        return await self.manager.add_plan(month, plan_text, priority, deadline, tags or [])

    async def complete_plan(self, plan_id: int) -> bool:
        """手动标记计划为已完成

        Args:
            plan_id: 计划 ID

        Returns:
            是否成功

        Examples:
            >>> success = await service.complete_plan(123)
        """
        return await self.manager.complete_plan(plan_id)

    async def cancel_plan(self, plan_id: int) -> bool:
        """取消计划

        Args:
            plan_id: 计划 ID

        Returns:
            是否成功

        Examples:
            >>> success = await service.cancel_plan(123)
        """
        return await self.manager.cancel_plan(plan_id)

    async def update_plan(self, plan_id: int, **updates: Any) -> bool:
        """更新计划

        Args:
            plan_id: 计划 ID
            **updates: 要更新的字段 (plan_text, priority, deadline, tags 等)

        Returns:
            是否成功

        Examples:
            >>> success = await service.update_plan(
            ...     plan_id=123,
            ...     plan_text="每周运动4次",
            ...     priority=5
            ... )
        """
        return await self.manager.update_plan(plan_id, **updates)
