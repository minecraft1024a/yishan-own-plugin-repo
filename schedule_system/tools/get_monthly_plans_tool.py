"""获取月度计划工具

让 LLM 可以查询当月的月度计划列表。
"""

from typing import Annotated, TYPE_CHECKING

from src.core.components.base.tool import BaseTool
from src.kernel.logger import get_logger

if TYPE_CHECKING:
    from ..plugin import ScheduleSystemPlugin

logger = get_logger("schedule_system.get_monthly_plans_tool", display="月度计划工具")


class GetMonthlyPlansTool(BaseTool):
    """获取月度计划工具

    允许 LLM 查询指定月份的活跃月度计划列表。
    默认查询当前月份，也可以指定其他月份。

    Examples:
        >>> # LLM 调用示例
        >>> success, result = await tool.execute()  # 查询当月
        >>> success, result = await tool.execute(month="2026-04")  # 查询指定月份
    """

    tool_name: str = "get_monthly_plans"
    tool_description: str = "获取指定月份的月度计划列表。用于查看你的月度目标和计划。默认查询当前月份。"

    def __init__(self, plugin: "ScheduleSystemPlugin"):
        """初始化工具

        Args:
            plugin: 插件实例
        """
        super().__init__(plugin)
        self.plugin: "ScheduleSystemPlugin" = plugin

    async def execute(
        self,
        month: Annotated[str | None, "目标月份，格式为 YYYY-MM，例如 '2026-03'。不提供则查询当前月份"] = None,
    ) -> tuple[Annotated[bool, "是否成功"], Annotated[str | list[dict], "返回结果"]]:
        """获取月度计划列表

        Args:
            month: 目标月份 (YYYY-MM)，默认为当前月份

        Returns:
            tuple[bool, str | list[dict]]: (是否成功, 计划列表或错误信息)

        Examples:
            >>> # 查询当月计划
            >>> success, plans = await tool.execute()
            >>> # 查询指定月份计划
            >>> success, plans = await tool.execute(month="2026-04")
            >>> if success and plans:
            ...     for plan in plans:
            ...         print(f"{plan['plan_text']} (优先级: {plan['priority']}, 已使用: {plan['usage_count']}次)")
        """
        try:
            # 获取 plan_service
            plan_service = self.plugin._plan_service
            if not plan_service:
                error_msg = "计划服务未初始化"
                logger.error(error_msg)
                return False, error_msg

            # 如果没有指定月份，使用当前月份
            if not month:
                from datetime import datetime

                month = datetime.now().strftime("%Y-%m")
                logger.debug(f"未指定月份，使用当前月份: {month}")

            # 调用服务获取月度计划
            plans = await plan_service.get_active_plans(month)

            if plans:
                # 格式化返回结果
                result = []
                for plan in plans:
                    result.append(
                        {
                            "id": plan.get("id"),
                            "plan_text": plan.get("plan_text"),
                            "priority": plan.get("priority"),
                            "status": plan.get("status"),
                            "usage_count": plan.get("usage_count", 0),
                            "deadline": plan.get("deadline"),
                            "tags": plan.get("tags", []),
                            "created_at": plan.get("created_at"),
                        }
                    )

                logger.info(f"查询月度计划成功: month={month}, count={len(result)}")
                return True, result
            else:
                # 该月份没有计划
                message = f"月份 {month} 还没有添加计划"
                logger.info(message)
                return True, message

        except Exception as e:
            # 其他错误
            error_msg = f"查询月度计划失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
