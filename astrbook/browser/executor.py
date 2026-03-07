"""动作执行器模块

负责解析和执行 AI 输出的动作
"""

from typing import TYPE_CHECKING

from src.kernel.logger import get_logger

if TYPE_CHECKING:
    from src.core.components.base.plugin import BasePlugin

logger = get_logger("astrbot.executor", display="动作执行器")


class ActionExecutor:
    """动作执行器

    将 AI 输出的 JSON 动作转换为实际的 API 调用
    """

    def __init__(self, plugin: "BasePlugin"):
        self.plugin = plugin
        self._service = None

    @property
    def service(self):
        """延迟获取 API 服务"""
        if self._service is None:
            from src.core.managers import get_service_manager

            service_manager = get_service_manager()
            service_sig = f"{self.plugin.plugin_name}:service:astrbot_api"
            self._service = service_manager.get_service(service_sig)
            if not self._service:
                raise RuntimeError(f"无法获取 AstrBot API 服务: {service_sig}")
        return self._service

    async def reply_thread(self, thread_id: int, content: str) -> tuple[bool, str]:
        """回复帖子主楼

        Returns:
            (success, detail)
        """
        try:
            result = await self.service.create_reply(thread_id, content)
            return True, f"回复ID: {result.get('id', 'unknown')}"
        except Exception as e:
            logger.error(f"回复帖子失败: {e}")
            return False, str(e)

    async def reply_floor(
        self,
        reply_id: int,
        content: str,
        reply_to_id: int | None = None,
        thread_id: int | None = None,
    ) -> tuple[bool, str]:
        """发送楼中楼回复

        Args:
            reply_id: 回复ID（可能是主楼层ID或楼中楼ID）
            content: 回复内容
            reply_to_id: @的用户ID
            thread_id: 帖子ID（用于查找主楼层ID，可选）

        Returns:
            (success, detail)
        """
        try:
            # 如果提供了thread_id，尝试查找主楼层ID
            main_floor_id = reply_id
            if thread_id:
                main_floor_id = await self._find_main_floor_id(thread_id, reply_id)
                if main_floor_id != reply_id:
                    logger.info(f"楼中楼 {reply_id} 所属主楼层 ID: {main_floor_id}")

            result = await self.service.send_sub_reply(
                reply_id=main_floor_id, content=content, reply_to_id=reply_to_id
            )
            return True, f"楼中楼ID: {result.get('id', 'unknown')}"
        except Exception as e:
            logger.error(f"发送楼中楼失败: {e}")
            return False, str(e)

    async def like(self, target_type: str, target_id: int) -> tuple[bool, str]:
        """点赞

        Args:
            target_type: "thread" 或 "reply"
            target_id: 目标 ID

        Returns:
            (success, detail)
        """
        try:
            if target_type == "thread":
                result = await self.service.like_thread(target_id)
            elif target_type == "reply":
                result = await self.service.like_reply(target_id)
            else:
                return False, f"未知的点赞目标类型: {target_type}"

            liked = result.get("liked", True)
            return True, "已点赞" if liked else "已取消点赞"
        except Exception as e:
            logger.error(f"点赞失败: {e}")
            return False, str(e)

    async def follow(self, user_id: int) -> tuple[bool, str]:
        """关注用户

        Returns:
            (success, detail)
        """
        try:
            await self.service.follow_user(user_id)
            return True, "关注成功"
        except Exception as e:
            logger.error(f"关注用户失败: {e}")
            return False, str(e)

    async def _find_main_floor_id(self, thread_id: int, reply_id: int) -> int:
        """从帖子详情中查找楼中楼所属的主楼层 ID

        Args:
            thread_id: 帖子ID
            reply_id: 回复ID（可能是主楼层或楼中楼）

        Returns:
            主楼层的 ID，如果找不到则返回原 reply_id
        """
        try:
            # 获取帖子详情
            thread_detail = await self.service.get_thread_detail(thread_id)

            # 先检查是否是主楼层ID
            for main_reply in thread_detail.get("replies", {}).get("items", []):
                if main_reply.get("id") == reply_id:
                    # 已经是主楼层ID，直接返回
                    return reply_id

            # 不是主楼层ID，在楼中楼中查找
            for main_reply in thread_detail.get("replies", {}).get("items", []):
                for sub_reply in main_reply.get("sub_replies", []):
                    if sub_reply.get("id") == reply_id:
                        # 找到了，返回主楼层ID
                        return main_reply.get("id")

            # 如果都找不到，返回原ID
            logger.warning(f"无法找到回复 {reply_id} 所属的主楼层，使用原ID")
            return reply_id

        except Exception as e:
            logger.error(f"查找主楼层ID失败: {e}，使用原ID")
            return reply_id
