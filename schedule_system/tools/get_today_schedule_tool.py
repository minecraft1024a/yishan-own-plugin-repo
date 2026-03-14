"""获取今日日程工具

让 LLM 可以查询今天的完整日程安排。
"""

from typing import Annotated, TYPE_CHECKING

from src.core.components.base.tool import BaseTool
from src.kernel.logger import get_logger

if TYPE_CHECKING:
    from ..plugin import ScheduleSystemPlugin

logger = get_logger("schedule_system.get_today_schedule_tool", display="今日日程工具")


class GetTodayScheduleTool(BaseTool):
    """获取今日日程工具

    允许 LLM 查询今天的完整日程安排列表。
    用于了解用户今天的所有计划安排。

    Examples:
        >>> # LLM 调用示例
        >>> success, result = await tool.execute()
        >>> if success:
        ...     for item in result:
        ...         print(f"{item['time_range']}: {item['activity']}")
    """

    tool_name: str = "get_today_schedule"
    tool_description: str = "获取今天的完整日程安排列表。用于查看你今天的所有活动计划。"

    def __init__(self, plugin: "ScheduleSystemPlugin"):
        """初始化工具

        Args:
            plugin: 插件实例
        """
        super().__init__(plugin)
        self.plugin: "ScheduleSystemPlugin" = plugin

    async def execute(
        self,
    ) -> tuple[Annotated[bool, "是否成功"], Annotated[str | list[dict], "返回结果"]]:
        """获取今天的完整日程

        Returns:
            tuple[bool, str | list[dict]]: (是否成功, 日程列表或错误信息)

        Examples:
            >>> success, schedule = await tool.execute()
            >>> if success and schedule:
            ...     for item in schedule:
            ...         print(f"{item['time_range']}: {item['activity']} (优先级: {item['priority']})")
        """
        try:
            # 获取 schedule_service
            schedule_service = self.plugin._schedule_service
            if not schedule_service:
                error_msg = "日程服务未初始化"
                logger.error(error_msg)
                return False, error_msg

            # 获取今天的日期
            from ..utils.time_utils import get_today_str

            today = get_today_str()

            # 调用服务获取今日日程
            schedule = await schedule_service.get_schedule(today)

            if schedule:
                # 格式化返回结果
                result = []
                for item in schedule:
                    result.append(
                        {
                            "id": item.get("id"),
                            "time_range": item.get("time_range"),
                            "activity": item.get("activity"),
                            "priority": item.get("priority"),
                            "tags": item.get("tags", []),
                            "is_completed": item.get("is_completed", False),
                        }
                    )

                logger.info(f"查询今日日程成功: date={today}, count={len(result)}")
                return True, result
            else:
                # 今天没有日程
                message = f"今天 ({today}) 还没有安排日程"
                logger.info(message)
                return True, message

        except Exception as e:
            # 其他错误
            error_msg = f"查询今日日程失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
