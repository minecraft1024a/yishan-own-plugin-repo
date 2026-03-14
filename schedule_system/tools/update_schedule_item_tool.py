"""更新日程项工具

让 LLM 可以根据日期和时间更新日程项的文字内容和优先度。
"""

from typing import Annotated, TYPE_CHECKING

from src.core.components.base.tool import BaseTool
from src.kernel.logger import get_logger

if TYPE_CHECKING:
    from ..plugin import ScheduleSystemPlugin

logger = get_logger("schedule_system.update_schedule_item_tool", display="更新日程工具")


class UpdateScheduleItemTool(BaseTool):
    """更新日程项工具

    允许 LLM 在对话中根据日期和时间更新日程项的活动内容和优先级。
    仅支持更新文字描述和优先度，不能修改时间、日期等其他属性。

    Examples:
        >>> # LLM 调用示例
        >>> success, result = await tool.execute(
        ...     date="2026-03-14",
        ...     time_range="14:00-15:00",
        ...     activity="会议（改为线上）",
        ...     priority=5
        ... )
    """

    tool_name: str = "update_schedule_item"
    tool_description: str = "更新指定日期和时间的日程项内容或优先级。用于修改你已有日程的描述或重要程度。"

    def __init__(self, plugin: "ScheduleSystemPlugin"):
        """初始化工具

        Args:
            plugin: 插件实例
        """
        super().__init__(plugin)
        self.plugin: "ScheduleSystemPlugin" = plugin

    async def execute(
        self,
        time_range: Annotated[str, "时间范围，格式为 HH:MM-HH:MM，例如 '14:00-15:00'"],
        activity: Annotated[str | None, "新的活动描述，1-200 个字符"] = None,
        priority: Annotated[int | None, "新的优先级，1-5，5 最高，3 中等，1 最低"] = None,
    ) -> tuple[Annotated[bool, "是否成功"], Annotated[str | dict, "返回结果"]]:
        """更新日程项

        Args:
            date: 日程日期 (YYYY-MM-DD)
            time_range: 时间范围 (HH:MM-HH:MM)
            activity: 新的活动描述（可选）
            priority: 新的优先级 1-5（可选）

        Returns:
            tuple[bool, str | dict]: (是否成功, 结果信息)

        Examples:
            >>> # 只更新活动描述
            >>> success, result = await tool.execute(
            ...     date="2026-03-14",
            ...     time_range="14:00-15:00",
            ...     activity="团队会议（改为线上）"
            ... )
            >>> # 只更新优先级
            >>> success, result = await tool.execute(
            ...     date="2026-03-14",
            ...     time_range="14:00-15:00",
            ...     priority=5
            ... )
            >>> # 同时更新两者
            >>> success, result = await tool.execute(
            ...     date="2026-03-14",
            ...     time_range="14:00-15:00",
            ...     activity="紧急会议",
            ...     priority=5
            ... )
        """
        try:
            # 验证：至少提供一个更新字段
            if activity is None and priority is None:
                error_msg = "必须至少提供 activity 或 priority 中的一个参数"
                logger.warning(error_msg)
                return False, error_msg

            # 获取 schedule_service
            schedule_service = self.plugin._schedule_service
            if not schedule_service:
                error_msg = "日程服务未初始化"
                logger.error(error_msg)
                return False, error_msg

            # 1. 获取指定日期的所有日程项
            from datetime import datetime

            now = datetime.now()
            date = now.strftime("%Y-%m-%d")
            schedule_items = await schedule_service.get_schedule(date=date)


            # 2. 查找匹配时间范围的日程项
            target_item = None
            for item in schedule_items:
                if item.get("time_range") == time_range:
                    target_item = item
                    break

            if not target_item:
                error_msg = f"未找到日期 {date} 时间 {time_range} 的日程项"
                logger.warning(error_msg)
                return False, error_msg

            item_id = target_item["id"]

            # 3. 构建更新字段
            updates = {}
            if activity is not None:
                # 验证活动描述
                if not activity or len(activity) > 200:
                    error_msg = "活动描述必须在 1-200 个字符之间"
                    logger.warning(error_msg)
                    return False, error_msg
                updates["activity"] = activity

            if priority is not None:
                # 验证优先级
                if priority < 1 or priority > 5:
                    error_msg = "优先级必须在 1-5 之间"
                    logger.warning(error_msg)
                    return False, error_msg
                updates["priority"] = priority

            # 4. 调用服务更新日程项
            success = await schedule_service.update_schedule_item(item_id, **updates)

            if not success:
                error_msg = f"更新日程项失败"
                logger.warning(error_msg)
                return False, error_msg

            # 构造成功响应
            result = {
                "date": date,
                "time_range": time_range,
                "original_activity": target_item.get("activity"),
                "updated_fields": updates,
                "status": "已更新",
            }

            logger.info(
                f"LLM 更新日程项成功: date={date}, time={time_range}, updates={updates}"
            )
            return True, result

        except Exception as e:
            # 其他错误
            error_msg = f"更新日程项失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
