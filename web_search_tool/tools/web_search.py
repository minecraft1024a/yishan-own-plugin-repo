"""
Web search tool implementation
"""

import asyncio
from typing import Annotated, Any, TYPE_CHECKING

from src.core.components.base.tool import BaseTool
from src.kernel.logger import get_logger
from src.core.components.types import ChatType

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

logger = get_logger("web_search_tool")


class WebSurfingTool(BaseTool):
    """
    网络搜索工具
    """

    chat_type = ChatType.ALL
    tool_name: str = "web_search"
    tool_description: str = (
        "联网搜索工具。使用场景：\n"
        "1. 用户问的问题你不确定答案、需要验证\n"
        "2. 涉及最新信息（新闻、产品、事件、时效性内容）\n"
        "3. 需要查找具体数据、事实、定义\n"
        "4. 用户明确要求搜索\n"
    )
    
    def __init__(self, plugin: "BasePlugin") -> None:
        super().__init__(plugin)
        
        # 获取配置对象
        from ..config import WebSearchConfig
        self.config = self.plugin.config if isinstance(self.plugin.config, WebSearchConfig) else None
        
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


    async def execute(
        self,
        query: Annotated[str, "要搜索的关键词或问题"],
        num_results: Annotated[int, "期望每个搜索引擎返回的搜索结果数量"] = 5,
        time_range: Annotated[str, "搜索时间范围：'any', 'week', 'month'"] = "any"
    ) -> tuple[bool, str | dict[str, Any]]:
        """执行网络搜索。

        Args:
            query: 要搜索的关键词或问题
            num_results: 期望每个搜索引擎返回的搜索结果数量，默认为5
            time_range: 指定搜索的时间范围，可以是 'any', 'week', 'month'。默认为 'any'

        Returns:
            tuple[bool, str | dict]: (是否成功, 搜索结果或错误信息)
        """
        if not query:
            return False, "搜索查询不能为空。"

        # 读取搜索配置（从插件配置中获取，而不是使用旧的 config_api）
        if self.config:
            enabled_engines = getattr(self.config.search, "enabled_engines", ["ddg"])
            search_strategy = getattr(self.config.search, "search_strategy", "single")
        else:
            enabled_engines = ["ddg"]
            search_strategy = "single"
        

        logger.info(f"开始搜索，策略: {search_strategy}, 启用引擎: {enabled_engines}, 查询: '{query}'")

        # 根据策略执行搜索
        try:
            if search_strategy == "parallel":
                result = await self._execute_parallel_search(query, num_results, time_range, enabled_engines)
            elif search_strategy == "fallback":
                result = await self._execute_fallback_search(query, num_results, time_range, enabled_engines)
            else:  # single
                result = await self._execute_single_search(query, num_results, time_range, enabled_engines)
            
            # 检查结果中是否有错误
            if isinstance(result, dict) and "error" in result:
                return False, result["error"]
            
            return True, result
            
        except Exception as e:
            logger.error(f"执行网络搜索时发生异常: {e}")
            return False, f"执行网络搜索时发生严重错误: {e!s}"


    async def _execute_parallel_search(
        self, query: str, num_results: int, time_range: str, enabled_engines: list[str]
    ) -> dict[str, Any]:
        """并行搜索策略：同时使用所有启用的搜索引擎"""
        search_tasks = []

        for engine_name in enabled_engines:
            engine = self.engines.get(engine_name)
            if engine and engine.is_available():
                search_tasks.append(engine.search(query, num_results, time_range))

        if not search_tasks:
            return {"error": "没有可用的搜索引擎。"}

        try:
            search_results_lists = await asyncio.gather(*search_tasks, return_exceptions=True)

            all_results = []
            for result in search_results_lists:
                if isinstance(result, list):
                    all_results.extend(result)
                elif isinstance(result, Exception):
                    logger.error(f"搜索时发生错误: {result}")

            # 去重并格式化
            unique_results = deduplicate_results(all_results)
            formatted_content = format_search_results(unique_results)

            return {
                "type": "web_search_result",
                "content": formatted_content,
            }

        except Exception as e:
            logger.error(f"执行并行网络搜索时发生异常: {e}")
            return {"error": f"执行网络搜索时发生严重错误: {e!s}"}


    async def _execute_fallback_search(
        self, query: str, num_results: int, time_range: str, enabled_engines: list[str]
    ) -> dict[str, Any]:
        """回退搜索策略：按顺序尝试搜索引擎，失败则尝试下一个"""

        for engine_name in enabled_engines:
            engine = self.engines.get(engine_name)
            if not engine or not engine.is_available():
                continue

            try:
                results = await engine.search(query, num_results, time_range)

                if results:  # 如果有结果，直接返回
                    formatted_content = format_search_results(results)
                    return {
                        "type": "web_search_result",
                        "content": formatted_content,
                    }

            except Exception as e:
                logger.warning(f"{engine_name} 搜索失败，尝试下一个引擎: {e}")
                continue

        return {"error": "所有搜索引擎都失败了。"}


    async def _execute_single_search(
        self, query: str, num_results: int, time_range: str, enabled_engines: list[str]
    ) -> dict[str, Any]:
        """单一搜索策略：只使用第一个可用的搜索引擎"""

        for engine_name in enabled_engines:
            engine = self.engines.get(engine_name)
            if not engine or not engine.is_available():
                continue

            try:
                results = await engine.search(query, num_results, time_range)

                if results:
                    formatted_content = format_search_results(results)
                    return {
                        "type": "web_search_result",
                        "content": formatted_content,
                    }

            except Exception as e:
                logger.error(f"{engine_name} 搜索失败: {e}")
                return {"error": f"{engine_name} 搜索失败: {e!s}"}

        return {"error": "没有可用的搜索引擎。"}
