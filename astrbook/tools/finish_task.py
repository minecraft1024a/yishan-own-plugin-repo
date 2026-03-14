"""任务结束工具

Agent 调用此工具表示当前任务已完成
"""

from typing import Annotated

from src.core.components.base.tool import BaseTool


class FinishTaskTool(BaseTool):
    """任务结束工具
    
    Agent 调用此工具表示本次任务已完成，应该退出循环
    """
    
    tool_name = "finish_task"
    tool_description = "结束当前 Agent 任务，在完成所有工作或达到配额上限时调用"
    
    async def execute(
        self,
        reason: Annotated[str, "结束任务的原因，例如'已完成今日社区活动目标'"]
    ) -> tuple[bool, dict]:
        """执行任务结束
        
        Args:
            reason: 结束原因
            
        Returns:
            (True, {"finished": True, "reason": reason})
        """
        return True, {
            "finished": True,
            "reason": reason
        }
