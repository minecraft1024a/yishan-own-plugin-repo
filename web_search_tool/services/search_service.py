"""
Web Search Service

提供搜索功能供其他插件调用的服务组件。
"""

import asyncio
from typing import Any, TYPE_CHECKING

from src.kernel.logger import get_logger
from src.core.components.base import BaseService

from ..engines.bing_engine import BingSearchEngine
from ..engines.ddg_engine import DDGSearchEngine
from ..engines.exa_engine import ExaSearchEngine
from ..engines.metaso_engine import MetasoSearchEngine
from ..engines.searxng_engine import SearXNGSearchEngine
from ..engines.serper_engine import SerperSearchEngine
from ..engines.tavily_engine import TavilySearchEngine
from ..utils.formatters import deduplicate_results, format_search_results

if TYPE_CHECKING:
    from src.core.components.base import BasePlugin

logger = get_logger("search_service")


class SearchService(BaseService):
    """
    网络搜索服务
    
    提供搜索功能供其他插件调用，支持多种搜索引擎和搜索策略。
    
    Examples:
        >>> # 从服务管理器获取服务
        >>> search_service = service_manager.get_service("web_search_tool:service:web_search")
        >>> results = await search_service.search("Python 最新版本")
        >>> print(results)
    """

    service_name: str = "web_search"
    service_description: str = "网络搜索服务，提供多引擎搜索功能"
    version: str = "1.0.0"

    def __init__(self, plugin: "BasePlugin") -> None:
        super().__init__(plugin)
        
        # 获取配置对象
        from ..config import WebSearchConfig
        self.config = plugin.config if isinstance(plugin.config, WebSearchConfig) else None
        
        # 初始化搜索引擎
        self.engines = {
            "exa": ExaSearchEngine(self.config),
            "tavily": TavilySearchEngine(self.config),
            "ddg": DDGSearchEngine(self.config),
            "bing": BingSearchEngine(self.config),
            "searxng": SearXNGSearchEngine(self.config),
            "metaso": MetasoSearchEngine(self.config),
            "serper": SerperSearchEngine(self.config),
        }
        
        logger.info("搜索服务已初始化")

    async def search(
        self,
        query: str,
        num_results: int = 5,
        time_range: str = "any",
        engine: str | None = None,
        strategy: str | None = None
    ) -> dict[str, Any]:
        """执行搜索。

        Args:
            query: 搜索查询
            num_results: 返回结果数量
            time_range: 时间范围 ('any', 'week', 'month')
            engine: 指定搜索引擎，None 则使用配置中的默认引擎
            strategy: 搜索策略 ('single', 'parallel', 'fallback')，None 则使用配置中的策略

        Returns:
            dict: 搜索结果
                {
                    "type": "web_search_result",
                    "content": "格式化的搜索结果",
                    "query": "原始查询",
                    "num_results": 实际返回数量
                }
                或错误时返回 {"error": "错误信息"}
        """
        if not query:
            return {"error": "搜索查询不能为空"}

        # 读取配置
        if self.config:
            enabled_engines = getattr(self.config.search, "enabled_engines", ["ddg"])
            search_strategy = strategy or getattr(self.config.search, "search_strategy", "single")
            default_engine = engine or getattr(self.config.search, "default_engine", "ddg")
        else:
            enabled_engines = [engine] if engine else ["ddg"]
            search_strategy = strategy or "single"
            default_engine = engine or "ddg"

        # 如果指定了引擎，优先使用指定的引擎
        if engine:
            enabled_engines = [engine]

        logger.info(f"执行搜索：'{query}'，策略：{search_strategy}，引擎：{enabled_engines}")

        try:
            if search_strategy == "parallel":
                result = await self._parallel_search(query, num_results, time_range, enabled_engines)
            elif search_strategy == "fallback":
                result = await self._fallback_search(query, num_results, time_range, enabled_engines)
            else:  # single
                result = await self._single_search(query, num_results, time_range, enabled_engines)
            
            # 添加查询信息到结果
            if "error" not in result:
                result["query"] = query
            
            return result

        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return {"error": f"搜索失败: {e!s}"}

    async def get_available_engines(self) -> list[str]:
        """获取所有可用的搜索引擎列表。

        Returns:
            list[str]: 可用引擎名称列表
        """
        available = []
        for name, engine in self.engines.items():
            is_avail = engine.is_available()
            if is_avail:
                available.append(name)
                logger.debug(f"  ✅ {name}: 可用")
            else:
                logger.debug(f"  ❌ {name}: 不可用")
        return available

    async def check_engine_status(self, engine_name: str) -> dict[str, Any]:
        """检查指定搜索引擎的状态。

        Args:
            engine_name: 引擎名称

        Returns:
            dict: 包含引擎状态信息的字典
        """
        engine = self.engines.get(engine_name)
        if not engine:
            return {
                "engine": engine_name,
                "exists": False,
                "available": False,
                "error": "引擎不存在"
            }
        
        return {
            "engine": engine_name,
            "exists": True,
            "available": engine.is_available(),
            "type": engine.__class__.__name__
        }

    async def _parallel_search(
        self, query: str, num_results: int, time_range: str, enabled_engines: list[str]
    ) -> dict[str, Any]:
        """并行搜索策略。"""
        search_tasks = []

        for engine_name in enabled_engines:
            engine = self.engines.get(engine_name)
            if not engine:
                logger.warning(f"引擎 '{engine_name}' 不存在")
                continue
            
            is_available = engine.is_available()
            logger.debug(f"引擎 '{engine_name}' 可用性检查: {is_available}")
            
            if is_available:
                search_tasks.append(engine.search(query, num_results, time_range))
            else:
                logger.warning(f"引擎 '{engine_name}' 不可用，跳过")

        if not search_tasks:
            logger.error(f"没有可用的搜索引擎。已启用引擎: {enabled_engines}")
            return {"error": "没有可用的搜索引擎"}

        try:
            search_results_lists = await asyncio.gather(*search_tasks, return_exceptions=True)

            all_results = []
            for result in search_results_lists:
                if isinstance(result, list):
                    all_results.extend(result)
                elif isinstance(result, Exception):
                    logger.error(f"搜索时发生错误: {result}")

            unique_results = deduplicate_results(all_results)
            formatted_content = format_search_results(unique_results)

            return {
                "type": "web_search_result",
                "content": formatted_content,
                "num_results": len(unique_results)
            }

        except Exception as e:
            logger.error(f"并行搜索失败: {e}")
            return {"error": f"并行搜索失败: {e!s}"}

    async def _fallback_search(
        self, query: str, num_results: int, time_range: str, enabled_engines: list[str]
    ) -> dict[str, Any]:
        """回退搜索策略。"""
        for engine_name in enabled_engines:
            engine = self.engines.get(engine_name)
            if not engine:
                logger.debug(f"引擎 '{engine_name}' 不存在")
                continue
            
            is_available = engine.is_available()
            if not is_available:
                logger.debug(f"引擎 '{engine_name}' 不可用")
                continue

            try:
                results = await engine.search(query, num_results, time_range)

                if results:
                    formatted_content = format_search_results(results)
                    return {
                        "type": "web_search_result",
                        "content": formatted_content,
                        "num_results": len(results),
                        "engine_used": engine_name
                    }

            except Exception as e:
                logger.warning(f"{engine_name} 搜索失败，尝试下一个引擎: {e}")
                continue

        return {"error": "所有搜索引擎都失败了"}

    async def _single_search(
        self, query: str, num_results: int, time_range: str, enabled_engines: list[str]
    ) -> dict[str, Any]:
        """单一搜索策略。"""
        logger.debug(f"单引擎搜索: {enabled_engines}")
        
        for engine_name in enabled_engines:
            engine = self.engines.get(engine_name)
            
            if not engine:
                logger.warning(f"引擎 '{engine_name}' 不存在")
                continue
                
            is_available = engine.is_available()
            if not is_available:
                logger.debug(f"引擎 '{engine_name}' 不可用")
                continue
            
            logger.debug(f"使用引擎 '{engine_name}' 搜索...")

            try:
                results = await engine.search(query, num_results, time_range)

                if results:
                    formatted_content = format_search_results(results)
                    return {
                        "type": "web_search_result",
                        "content": formatted_content,
                        "num_results": len(results),
                        "engine_used": engine_name
                    }
                else:
                    logger.warning(f" 引擎 '{engine_name}' 返回空结果")

            except Exception as e:
                logger.error(f"引擎 '{engine_name}' 搜索失败: {e}")
                return {"error": f"{engine_name} 搜索失败: {e!s}"}

        logger.warning(f"所有引擎不可用: {enabled_engines}")
        return {"error": "没有可用的搜索引擎"}
