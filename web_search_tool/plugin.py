"""
Web Search Tool Plugin

一个功能强大的网络搜索和URL解析插件，支持多种搜索引擎和解析策略。
"""

from typing import ClassVar

from src.kernel.logger import get_logger
from src.core.components import BasePlugin, register_plugin

from .config import WebSearchConfig
from .tools.web_search import WebSurfingTool
from .services.search_service import SearchService

logger = get_logger("web_search_plugin")


@register_plugin
class WebSearchPlugin(BasePlugin):
    """
    网络搜索工具插件

    提供网络搜索和URL解析功能，支持多种搜索引擎：
    - Exa (需要API密钥)
    - Tavily (需要API密钥)
    - Metaso (需要API密钥)
    - DuckDuckGo (免费)
    - Bing (免费)
    """

    # 插件基本信息（必需）
    plugin_name: str = "web_search_tool"  # 必须与 manifest.json 中的 name 一致
    plugin_description: str = "网络搜索和URL解析工具插件"
    plugin_version: str = "1.0.0"
    
    # 插件配置
    configs: list[type] = [WebSearchConfig]
    
    # 依赖组件
    dependent_components: list[str] = []

    async def on_plugin_loaded(self) -> None:
        """
        插件加载完成后的生命周期钩子

        在此初始化所有搜索引擎，确保不阻塞插件注册流程
        """
        logger.info("🚀 正在初始化所有搜索引擎...")
        try:
            from .engines.bing_engine import BingSearchEngine
            from .engines.ddg_engine import DDGSearchEngine
            from .engines.exa_engine import ExaSearchEngine
            from .engines.metaso_engine import MetasoSearchEngine
            from .engines.searxng_engine import SearXNGSearchEngine
            from .engines.serper_engine import SerperSearchEngine
            from .engines.tavily_engine import TavilySearchEngine

            # 获取配置（类型安全）
            config = self.config if isinstance(self.config, WebSearchConfig) else None

            # 实例化所有搜索引擎，传递配置对象
            exa_engine = ExaSearchEngine(config)
            tavily_engine = TavilySearchEngine(config)
            ddg_engine = DDGSearchEngine(config)
            bing_engine = BingSearchEngine(config)
            searxng_engine = SearXNGSearchEngine(config)
            metaso_engine = MetasoSearchEngine(config)
            serper_engine = SerperSearchEngine(config)

            # 报告每个引擎的状态
            engines_status = {
                "Exa": exa_engine.is_available(),
                "Tavily": tavily_engine.is_available(),
                "DuckDuckGo": ddg_engine.is_available(),
                "Bing": bing_engine.is_available(),
                "SearXNG": searxng_engine.is_available(),
                "Metaso": metaso_engine.is_available(),
                "Serper": serper_engine.is_available(),
            }

            available_engines = [name for name, available in engines_status.items() if available]
            unavailable_engines = [name for name, available in engines_status.items() if not available]

            if available_engines:
                logger.info(f"✅ 可用搜索引擎: {', '.join(available_engines)}")
            if unavailable_engines:
                logger.info(f"❌ 不可用搜索引擎: {', '.join(unavailable_engines)}")

        except Exception as e:
            logger.error(f"❌ 搜索引擎初始化失败: {e}", exc_info=True)

    def get_components(self) -> list[type]:
        """
        获取插件组件列表

        Returns:
            插件内所有组件类的列表
        """
        components = []

        # 从配置读取组件启用状态
        if self.config and isinstance(self.config, WebSearchConfig):
            if self.config.components.enable_web_search_tool:
                components.append(WebSurfingTool)
            if self.config.components.enable_web_search_service:
                components.append(SearchService)
        else:
            # 如果没有配置，默认启用所有组件
            components.extend([WebSurfingTool, SearchService])

        return components
