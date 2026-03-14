"""AstrBot 插件主类"""

from src.core.components.base import BasePlugin
from src.core.components.loader import register_plugin
from .adapter import AstrBotAdapter
from .chatter import AstrBotChatter
from .service import AstrBotService
from .config import AstrBotConfig
from .community_agent import AstrBookCommunityAgent
from src.kernel.logger import get_logger

logger = get_logger(name="AstrBot 论坛集成插件")


@register_plugin
class AstrBotPlugin(BasePlugin):
    """AstrBot 论坛集成插件"""

    plugin_name = "astrbot"
    plugin_description = "AstrBot 论坛集成，支持自动回复和主动发帖"
    version = "1.0.0"
    author = "Neo-MoFox Team"
    configs = [AstrBotConfig]

    def get_components(self) -> list[type]:
        """
        注册相对应的插件组件
        """
        components = []
        if self.config.agent.enabled:
            components.append(AstrBookCommunityAgent)
        if self.config.polling.enabled:
            components.append(AstrBotAdapter)
        components.append(AstrBotChatter)
        components.append(AstrBotService)
        return components

    async def on_plugin_loaded(self):
        """插件加载时执行"""
        logger.info(f"[{self.plugin_name}] 插件加载完成")

        # 验证配置
        bot_token = self.config.api.bot_token
        if not bot_token:
            raise ValueError("缺少 api.bot_token 配置，请在 config.toml 中设置")


        # === 新架构：社区活动 Agent ===
        if self.config.agent.interval_enabled:
            logger.info(f"[{self.plugin_name}] 检测到 Agent 模式已启用")
            
            # 初始化状态管理器
            from .state_manager import init_state_manager
            self.state_manager = init_state_manager(self)
            
            # 创建 Agent 实例
            from .community_agent import AstrBookCommunityAgent
            self.community_agent = AstrBookCommunityAgent(
                stream_id="astrbot_community",
                plugin=self
            )
            
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
                f"[{self.plugin_name}] 社区活动 Agent 已启动，"
                f"间隔: {self.config.agent.interval_minutes} 分钟"
            )

    async def _agent_callback(self):
        """unified_scheduler 的 Agent 回调函数"""
        try:
            logger.info("🤖 AstrBook Agent 开始执行社区活动任务")
            
            import asyncio
            
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
                f" Agent 任务超时（{self.config.agent.decision_timeout}秒），"
                "强制结束"
            )
        except Exception as e:
            logger.error(f"Agent 任务异常: {e}")

    async def on_plugin_unloaded(self):
        """插件卸载时执行"""

        # 关闭 AstrBot API 服务的连接
        try:
            from src.core.managers import get_service_manager

            service_manager = get_service_manager()
            service_sig = f"{self.plugin_name}:service:astrbot_api"
            service = service_manager.get_service(service_sig)

            if service:
                await service.close()
                logger.info(f"[{self.plugin_name}] AstrBot服务连接已关闭")
        except Exception as e:
            logger.error(f"[{self.plugin_name}] 关闭服务连接时出错: {e}", exc_info=e)

        logger.info(f"[{self.plugin_name}] 插件已卸载")
