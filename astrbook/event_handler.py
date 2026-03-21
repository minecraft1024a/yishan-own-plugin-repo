"""AstrBot 启动事件处理器

在系统启动时初始化 Agent 调度器
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from src.core.components.base.event_handler import BaseEventHandler
from src.core.components.types import EventType
from src.kernel.event.core import EventDecision
from src.kernel.logger import get_logger

if TYPE_CHECKING:
    from .plugin import AstrBotPlugin

logger = get_logger(name="AstrBot 事件处理器")


class AstrBotStartupEventHandler(BaseEventHandler):
    """AstrBot 启动事件处理器
    
    在系统启动完成后执行插件初始化逻辑：
    - 验证配置
    - 初始化状态管理器
    - 创建社区 Agent 实例
    - 注册定时调度任务
    """

    handler_name = "astrbot_startup"
    handler_description = "AstrBot 插件启动初始化，配置 Agent 调度器"
    weight = 10
    intercept_message = False
    init_subscribe = [EventType.ON_START]

    def __init__(self, plugin: "AstrBotPlugin") -> None:
        """初始化事件处理器
        
        Args:
            plugin: 父插件实例（仅用于访问配置和传递给子组件）
        """
        super().__init__(plugin)
        self.plugin = plugin
        self.config = plugin.config
        self.community_agent = None  # 延迟初始化

    async def execute(
        self,
        event_name: str,
        params: dict[str, Any],
    ) -> tuple[EventDecision, dict[str, Any]]:
        """处理系统启动事件
        
        Args:
            event_name: 事件名称（ON_START）
            params: 事件参数
            
        Returns:
            事件决策和更新后的参数
        """
        try:
            logger.info(f"[{self.plugin.plugin_name}] 插件启动初始化开始")

            # 验证配置
            bot_token = self.config.api.bot_token
            if not bot_token:
                error_msg = "缺少 api.bot_token 配置，请在 config.toml 中设置"
                logger.error(f"[{self.plugin.plugin_name}] {error_msg}")
                raise ValueError(error_msg)

            # === 社区活动 Agent 初始化 ===
            if self.config.agent.interval_enabled:
                await self._initialize_agent()
            else:
                logger.info(f"[{self.plugin.plugin_name}] Agent 模式未启用，跳过调度器初始化")

            logger.info(f"[{self.plugin.plugin_name}] 插件启动初始化完成")

        except Exception as exc:
            logger.error(
                f"[{self.plugin.plugin_name}] 启动初始化失败: {exc}",
                exc_info=True
            )

        # 始终返回 SUCCESS，不阻塞其他事件处理器
        return EventDecision.SUCCESS, params

    async def _initialize_agent(self) -> None:
        """初始化社区活动 Agent 和调度器"""
        try:
            logger.info(f"[{self.plugin.plugin_name}] 检测到 Agent 模式已启用")

            # 初始化状态管理器（单例）
            from .state_manager import init_state_manager
            init_state_manager(self.plugin)

            # 创建 Agent 实例
            from .community_agent import AstrBookCommunityAgent
            self.community_agent = AstrBookCommunityAgent(
                stream_id="astrbot_community",
                plugin=self.plugin
            )

            # 立即执行一次（首次启动）
            logger.info(f"[{self.plugin.plugin_name}] 执行首次 Agent 任务")
            await self._agent_callback()

            # 注册到 unified_scheduler
            from src.kernel.scheduler import get_unified_scheduler, TriggerType

            interval_seconds = self.config.agent.interval_minutes * 60

            await get_unified_scheduler().create_schedule(
                callback=self._agent_callback,
                trigger_type=TriggerType.TIME,
                trigger_config={"delay_seconds": interval_seconds},
                is_recurring=True,
                task_name="astrbot_community_agent",
            )

            logger.info(
                f"[{self.plugin.plugin_name}] 社区活动 Agent 已启动，"
                f"间隔: {self.config.agent.interval_minutes} 分钟"
            )

        except Exception as exc:
            logger.error(
                f"[{self.plugin.plugin_name}] Agent 初始化失败: {exc}",
                exc_info=True
            )
            raise

    async def _agent_callback(self) -> None:
        """unified_scheduler 的 Agent 回调函数
        
        执行社区活动 Agent 任务，包含超时控制和错误处理
        """
        try:
            # 确保 StateManager 已初始化（防止插件重载后单例丢失）
            from .state_manager import get_state_manager, init_state_manager
            try:
                get_state_manager()
            except RuntimeError:
                logger.warning("StateManager 未初始化，正在重新初始化...")
                init_state_manager(self.plugin)
            
            logger.info("🤖 AstrBook Agent 开始执行社区活动任务")

            # 设置超时
            timeout = self.config.agent.decision_timeout
            success, result = await asyncio.wait_for(
                self.community_agent.execute(),
                timeout=timeout
            )

            if success:
                logger.info(f"✅ Agent 任务完成: {result}")
            else:
                logger.error(f"❌ Agent 任务失败: {result}")

        except asyncio.TimeoutError:
            logger.error(
                f"⏱️ Agent 任务超时（{self.config.agent.decision_timeout}秒），"
                "强制结束"
            )
        except Exception as exc:
            logger.error(f"❌ Agent 任务异常: {exc}", exc_info=True)
