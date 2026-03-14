"""历史管理工具

提供查询每日配额和行为历史的接口
"""

from typing import Annotated, TYPE_CHECKING

from src.core.components.base.tool import BaseTool
from ..state_manager import get_state_manager

if TYPE_CHECKING:
    from ..plugin import AstrBotPlugin


class HistoryManagerTool(BaseTool):
    """历史管理工具
    
    查询今日配额使用情况和剩余配额
    """
    
    tool_name = "history_manager"
    tool_description = "查询今日活动配额使用情况，包括发帖、回复、点赞的次数和剩余配额"
    
    def __init__(self, plugin: "AstrBotPlugin"):
        super().__init__(plugin)
        self.state_manager = get_state_manager()
    
    async def execute(
        self,
        query_type: Annotated[
            str,
            "查询类型：GET_SUMMARY（获取完整摘要）| CHECK_QUOTA（检查是否还能操作）"
        ] = "GET_SUMMARY"
    ) -> tuple[bool, dict]:
        """执行历史查询
        
        Args:
            query_type: 查询类型
            
        Returns:
            (成功标志, 结果字典)
        """
        try:
            state = await self.state_manager.get_today_stats()
            config = self.plugin.config.agent
            
            if query_type == "GET_SUMMARY":
                # 返回完整摘要
                return True, {
                    "date": state["date"],
                    "posts_today": state["post_count"],
                    "replies_today": state["reply_count"],
                    "likes_today": state["like_count"],
                    "quota_remaining": {
                        "posts": config.max_posts_per_day - state["post_count"],
                        "replies": config.max_replies_per_day - state["reply_count"],
                        "likes": config.max_likes_per_day - state["like_count"]
                    },
                    "summary": await self.state_manager.get_quota_summary()
                }
            
            elif query_type == "CHECK_QUOTA":
                # 检查配额状态
                can_post = await self.state_manager.can_post()
                can_reply = await self.state_manager.can_reply()
                can_like = await self.state_manager.can_like()
                
                return True, {
                    "can_post": can_post,
                    "can_reply": can_reply,
                    "can_like": can_like,
                    "all_quota_reached": not (can_post or can_reply or can_like)
                }
            
            else:
                return False, {"error": f"未知的查询类型: {query_type}"}
                
        except Exception as e:
            return False, {"error": f"查询历史失败: {e}"}
