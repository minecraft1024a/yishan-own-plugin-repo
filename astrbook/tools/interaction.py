"""互动执行工具

执行具体的互动动作：回复、点赞、关注等
"""

from typing import Annotated, TYPE_CHECKING

from src.core.components.base.tool import BaseTool
from src.kernel.logger import get_logger
from ..state_manager import get_state_manager

if TYPE_CHECKING:
    from ..plugin import AstrBotPlugin

logger = get_logger("astrbot.interaction_tool", display="互动工具")


class InteractionTool(BaseTool):
    """互动执行工具
    
    执行回复、点赞、关注等互动动作
    """
    
    tool_name = "interaction"
    tool_description = "执行论坛互动动作，包括回复帖子、点赞、关注用户等"
    
    def __init__(self, plugin: "AstrBotPlugin"):
        super().__init__(plugin)
        self.state_manager = get_state_manager()
    
    async def execute(
        self,
        action: Annotated[str, "动作类型：REPLY（回复）| LIKE（点赞）| FOLLOW（关注）"],
        target_id: Annotated[str, "目标 ID（帖子 ID 或用户 ID）"],
        content: Annotated[str, "回复内容（REPLY 动作必需）"] = "",
        reply_to_floor: Annotated[int, "楼中楼回复的层 ID（可选）"] = 0
    ) -> tuple[bool, dict]:
        """执行互动动作
        
        Args:
            action: 动作类型
            target_id: 目标 ID
            content: 回复内容
            reply_to_floor: 楼中楼 ID
            
        Returns:
            (成功标志, 结果字典)
        """
        try:
            # 获取 API 服务
            from src.core.managers import get_service_manager
            
            service_manager = get_service_manager()
            service_sig = f"{self.plugin.plugin_name}:service:astrbot_api"
            api_service = service_manager.get_service(service_sig)
            
            if not api_service:
                return False, {"error": f"无法获取 AstrBot API 服务: {service_sig}"}
            
            # 根据动作类型执行
            if action == "REPLY":
                # 检查配额
                if not await self.state_manager.can_reply():
                    state = await self.state_manager.get_today_stats()
                    return False, {
                        "error": "已达到每日回复上限",
                        "replies_today": state["reply_count"]
                    }
                
                if not content:
                    return False, {"error": "回复内容不能为空"}
                
                # 执行回复
                if reply_to_floor:
                    # 楼中楼回复
                    result = await api_service.create_floor_reply(
                        reply_id=reply_to_floor,
                        content=content
                    )
                else:
                    # 主楼回复
                    result = await api_service.create_reply(
                        thread_id=target_id,
                        content=content
                    )
                
                # 更新配额
                await self.state_manager.increment_count("reply_count")
                
                logger.info(f"成功回复帖子 {target_id}")
                
                return True, {
                    "action": "REPLY",
                    "success": True,
                    "reply_id": result.get("id"),
                    "detail": "回复成功"
                }
            
            elif action == "LIKE":
                # 检查配额
                if not await self.state_manager.can_like():
                    state = await self.state_manager.get_today_stats()
                    return False, {
                        "error": "已达到每日点赞上限",
                        "likes_today": state["like_count"]
                    }
                
                # 执行点赞（帖子或回复）
                result = await api_service.like_thread(thread_id=target_id)
                
                # 更新配额
                await self.state_manager.increment_count("like_count")
                
                logger.info(f"成功点赞 {target_id}")
                
                return True, {
                    "action": "LIKE",
                    "success": True,
                    "detail": "点赞成功"
                }
            
            elif action == "FOLLOW":
                # 关注用户
                result = await api_service.follow_user(user_id=target_id)
                
                logger.info(f"成功关注用户 {target_id}")
                
                return True, {
                    "action": "FOLLOW",
                    "success": True,
                    "detail": "关注成功"
                }
            
            else:
                return False, {"error": f"未知的动作类型: {action}"}
            
        except Exception as e:
            logger.error(f"执行互动失败 ({action} {target_id}): {e}", exc_info=True)
            return False, {"error": f"执行互动失败: {e}"}
