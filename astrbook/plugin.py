"""AstrBot 插件主类"""

from src.core.components.base import BasePlugin
from src.core.components.loader import register_plugin
from .adapter import AstrBotAdapter
from .chatter import AstrBotChatter
from .service import AstrBotService
from .config import AstrBotConfig
from .community_agent import AstrBookCommunityAgent
from .event_handler import AstrBotStartupEventHandler
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
        components.append(AstrBotStartupEventHandler)
        return components

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
