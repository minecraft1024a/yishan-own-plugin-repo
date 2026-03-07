"""AstrBot Adapter 组件"""

import asyncio
from typing import TYPE_CHECKING, Any

from mofox_wire import CoreSink, MessageBuilder, MessageEnvelope

from src.core.components.base import BaseAdapter
from src.kernel.concurrency import get_task_manager
from src.kernel.logger import get_logger

if TYPE_CHECKING:
    from src.core.components.base.plugin import BasePlugin


class AstrBotAdapter(BaseAdapter):
    """AstrBot 论坛适配器"""

    adapter_name = "astrbot_adapter"
    adapter_version = "1.0.0"
    adapter_description = "AstrBot 论坛通知轮询适配器"
    platform = "astrbot"
    dependencies = ["astrbot:service:astrbot_api"]

    def __init__(
        self, core_sink: CoreSink, plugin: "BasePlugin | None" = None, **kwargs: Any
    ):
        super().__init__(core_sink, plugin, **kwargs)
        self.interval = plugin.config.polling.interval if plugin else 10
        self.batch_size = plugin.config.polling.batch_size if plugin else 20
        self.logger = get_logger("astrbot_adapter")
        self._poll_task_info = None
        self.service = None

    async def on_adapter_loaded(self) -> None:
        """适配器加载时执行"""
        self.logger.info(f"[{self.adapter_name}] 适配器加载完成")

        # 获取 Service
        from src.core.managers import get_service_manager

        service_manager = get_service_manager()
        service_sig = (
            f"{self.plugin.plugin_name}:service:astrbot_api"
            if self.plugin
            else "astrbot:service:astrbot_api"
        )
        self.service = service_manager.get_service(service_sig)

        if not self.service:
            raise RuntimeError(f"无法获取 AstrBot API 服务: {service_sig}")

        # 使用系统任务管理器启动轮询任务
        tm = get_task_manager()
        self._poll_task_info = tm.create_task(
            self._poll_loop(),
            name=f"{self.adapter_name}_poll",
            daemon=True,
        )
        self.logger.info(f"[{self.adapter_name}] 开始轮询通知")

    async def on_adapter_unloaded(self) -> None:
        """适配器卸载时执行"""
        # 使用系统任务管理器停止轮询任务
        if self._poll_task_info:
            tm = get_task_manager()
            try:
                tm.cancel_task(self._poll_task_info.task_id)
            except Exception:
                pass
            self._poll_task_info = None

        self.logger.info(f"[{self.adapter_name}] 适配器已卸载")

    async def _poll_loop(self):
        """轮询循环"""
        consecutive_errors = 0

        while self._running:
            try:
                assert self.service is not None
                # 获取未读通知
                notifications = await self.service.get_notifications(
                    page=1, is_read=False
                )
                # 成功后重置错误计数

                if notifications.get("items"):
                    self.logger.info(f"获取到 {len(notifications['items'])} 条未读通知")

                    # 处理每条通知
                    notification_ids = []
                    for notif in notifications["items"]:
                        if notif["type"] in ["reply", "sub_reply"]:
                            # 转换为 MessageEnvelope 并发送到核心
                            envelope = await self.from_platform_message(notif)
                            await self.core_sink.send(envelope)
                            notification_ids.append(notif["id"])
                        else:
                            notification_ids.append(notif["id"])
                            continue

                    # 标记已读
                    if notification_ids and self.plugin.config.polling.auto_mark_read:
                        await self.service.mark_notifications_read(notification_ids)

            except Exception as e:
                self.logger.error(f"轮询出错: {e}", exc_info=True)

            await asyncio.sleep(self.interval)

    async def from_platform_message(self, raw: Any) -> MessageEnvelope:
        """将 AstrBot 通知转换为 MessageEnvelope"""
        # raw 是通知对象
        notif = raw

        # 使用 MessageBuilder 构建消息
        msg_builder = MessageBuilder()

        # 从通知中提取用户信息
        from_user = notif.get("from_user", {})
        # AstrBot API 可能返回 id 或 user_id，尝试两者
        user_id = str(from_user.get("id") or from_user.get("user_id") or "")

        # 如果还是没有 user_id，使用一个默认值或从其他地方获取
        if not user_id:
            # 尝试从通知 ID 生成一个用户标识
            user_id = f"astrbot_user_{notif.get('id', 'unknown')}"
            self.logger.warning(f"无法从通知中提取 user_id，使用生成的 ID: {user_id}")

        user_nickname = from_user.get("nickname", "未知用户")

        # 获取帖子/回复 ID
        thread_id = notif.get("thread_id", "")
        message_id = f"astrbot_{notif['id']}"

        # 构建消息
        (
            msg_builder.direction("incoming")
            .message_id(message_id)
            .from_user(
                user_id=user_id,
                platform=self.platform,
                nickname=user_nickname,
            )
            .from_group(
                group_id=f"thread_{thread_id}",
                platform=self.platform,
                name=notif.get("thread_title", f"帖子 {thread_id}"),
            )
            .format_info(
                content_format=["text"],
                accept_format=["text", "image"],
            )
        )

        # 构建消息段
        content = notif.get("content_preview", "")
        if not content:
            content = "[空消息]"

        msg_builder.seg_list([{"type": "text", "data": content}])

        # 添加自定义元数据
        envelope = msg_builder.build()
        envelope["message_info"]["extra"] = {
            "type": notif.get("type"),
            "thread_id": thread_id,
            "reply_id": notif.get("reply_id"),
            "from_user": from_user,
            "timestamp": notif.get("created_at"),
        }

        return envelope

    def is_connected(self) -> bool:
        """检查连接状态"""
        # 检查 service 是否可用
        return self.service is not None and self.service is not None
