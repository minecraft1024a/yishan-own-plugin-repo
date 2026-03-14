"""添加月度计划工具

让 LLM 可以直接添加月度计划的 Tool 组件。
"""

from typing import Annotated, TYPE_CHECKING

from src.core.components.base.tool import BaseTool
from src.kernel.logger import get_logger

if TYPE_CHECKING:
    from ..plugin import ScheduleSystemPlugin

logger = get_logger("schedule_system.add_plan_tool", display="添加计划工具")


class AddPlanTool(BaseTool):
    """添加月度计划工具

    允许 LLM 在对话中直接添加月度计划到系统中。

    Examples:
        >>> # LLM 调用示例
        >>> success, result = await tool.execute(
        ...     month="2026-03",
        ...     plan_text="每周运动3次",
        ...     priority=4,
        ...     tags=["健康", "运动"]
        ... )
    """

    tool_name: str = "add_monthly_plan"
    tool_description: str = "添加月度计划到系统中。用于记录你的目标、计划或待办事项。"

    def __init__(self, plugin: "ScheduleSystemPlugin"):
        """初始化工具

        Args:
            plugin: 插件实例
        """
        super().__init__(plugin)
        self.plugin: "ScheduleSystemPlugin" = plugin

    async def execute(
        self,
        plan_text: Annotated[str, "计划内容描述，1-500 个字符"],
        priority: Annotated[int, "优先级，1-5，5 最高，3 中等，1 最低"] = 3,
        deadline: Annotated[str | None, "可选的截止日期，格式为 YYYY-MM-DD"] = None,
        tags: Annotated[list[str] | None, "可选的标签列表，例如 ['学习', '工作']"] = None,
    ) -> tuple[Annotated[bool, "是否成功"], Annotated[str | dict, "返回结果"]]:
        """添加月度计划

        Args:
            month: 目标月份 (YYYY-MM)
            plan_text: 计划内容
            priority: 优先级 1-5
            deadline: 截止日期 (YYYY-MM-DD，可选)
            tags: 标签列表

        Returns:
            tuple[bool, str | dict]: (是否成功, 结果信息)

        Examples:
            >>> success, result = await tool.execute(
            ...     month="2026-03",
            ...     plan_text="完成项目文档",
            ...     priority=5,
            ...     deadline="2026-03-31",
            ...     tags=["工作", "文档"]
            ... )
        """
        try:
            # 获取 plan_service
            plan_service = self.plugin._plan_service
            if not plan_service:
                error_msg = "计划服务未初始化"
                logger.error(error_msg)
                return False, error_msg

            from datetime import datetime

            now = datetime.now()
            month = now.strftime("%Y-%m")

            # 调用服务添加计划
            plan_id = await plan_service.add_plan(
                month=month,
                plan_text=plan_text,
                priority=priority,
                deadline=deadline,
                tags=tags or [],
            )

            # 构造成功响应
            result = {
                "plan_id": plan_id,
                "month": month,
                "plan_text": plan_text,
                "priority": priority,
                "status": "已添加",
            }

            logger.info(f"LLM 添加月度计划成功: id={plan_id}, month={month}")
            return True, result

        except ValueError as e:
            # 验证错误
            error_msg = f"添加计划失败（参数错误）: {str(e)}"
            logger.warning(error_msg)
            return False, error_msg

        except Exception as e:
            # 其他错误
            error_msg = f"添加计划失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
