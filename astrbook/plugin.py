"""AstrBot 插件主类"""

from src.core.components.base import BasePlugin
from src.core.components.loader import register_plugin
from .adapter import AstrBotAdapter
from .chatter import AstrBotChatter
from .service import AstrBotService
from .config import AstrBotConfig
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

        # 注册浏览器提示词模板
        from .browser import register_prompts

        register_prompts()

        # 启动定时发帖任务（如果启用）
        if self.config.poster.enabled:
            from .post_scheduler import PostScheduler

            self.post_scheduler = PostScheduler(self)
            await self.post_scheduler.start()
            logger.info(f"[{self.plugin_name}] 定时发帖任务已启动")

        # 启动帖子浏览器（如果启用）
        if self.config.browser.enabled:
            from .browser import ThreadBrowser

            self.thread_browser = ThreadBrowser(self)
            await self.thread_browser.start()
            logger.info(f"[{self.plugin_name}] 帖子浏览器已启动")

    async def on_plugin_unloaded(self):
        """插件卸载时执行"""
        # 停止帖子浏览器
        if hasattr(self, "thread_browser"):
            await self.thread_browser.stop()
            logger.info(f"[{self.plugin_name}] 帖子浏览器已停止")

        # 停止定时发帖任务
        if hasattr(self, "post_scheduler"):
            await self.post_scheduler.stop()

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
