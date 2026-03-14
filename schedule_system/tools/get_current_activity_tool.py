"""获取当前活动工具

让 LLM 可以查询当前时间正在进行的活动。
"""

from typing import Annotated, TYPE_CHECKING

from src.core.components.base.tool import BaseTool
from src.kernel.logger import get_logger

if TYPE_CHECKING:
    from ..plugin import ScheduleSystemPlugin

logger = get_logger("schedule_system.get_current_activity_tool", display="当前活动工具")


class GetCurrentActivityTool(BaseTool):
    """获取当前活动工具

    允许 LLM 查询当前时间正在进行的日程活动。
    用于了解用户当前应该在做什么事情。

    Examples:
        >>> # LLM 调用示例
        >>> success, result = await tool.execute()
        >>> if success and result:
        ...     print(f"当前活动: {result['activity']}")
    """

    tool_name: str = "get_current_activity"
    tool_description: str = "获取当前时间正在进行的日程活动。用于了解你现在正在做什么。"

    def __init__(self, plugin: "ScheduleSystemPlugin"):
        """初始化工具

        Args:
            plugin: 插件实例
        """
        super().__init__(plugin)
        self.plugin: "ScheduleSystemPlugin" = plugin

    async def execute(
        self,
    ) -> tuple[Annotated[bool, "是否成功"], Annotated[str | dict | None, "返回结果"]]:
        """获取当前正在进行的活动

        Returns:
            tuple[bool, str | dict | None]: (是否成功, 当前活动信息或提示)

        Examples:
            >>> success, result = await tool.execute()
            >>> if result:
            ...     print(f"{result['time_range']}: {result['activity']}")
            >>> else:
            ...     print("当前没有安排活动")
        """
        try:
            # 获取 schedule_service
            schedule_service = self.plugin._schedule_service
            if not schedule_service:
                error_msg = "日程服务未初始化"
                logger.error(error_msg)
                return False, error_msg

            # 调用服务获取当前活动
            current_activity = await schedule_service.get_current_activity()

            if current_activity:
                # 格式化返回结果
                result = {
                    "id": current_activity.get("id"),
                    "time_range": current_activity.get("time_range"),
                    "activity": current_activity.get("activity"),
                    "priority": current_activity.get("priority"),
                    "tags": current_activity.get("tags", []),
                    "is_completed": current_activity.get("is_completed", False),
                }
                logger.info(f"查询当前活动成功: {result['activity']}")
                return True, result
            else:
                # 当前没有活动
                message = "当前时间段没有安排活动"
                logger.info(message)
                return True, message

        except Exception as e:
            # 其他错误
            error_msg = f"查询当前活动失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
