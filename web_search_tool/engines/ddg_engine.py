"""
DuckDuckGo search engine implementation
"""

from typing import Any, TYPE_CHECKING

from asyncddgs import aDDGS

from src.kernel.logger import get_logger

from .base import BaseSearchEngine

if TYPE_CHECKING:
    from ..config import WebSearchConfig

logger = get_logger("ddg_engine")


class DDGSearchEngine(BaseSearchEngine):
    """
    DuckDuckGo搜索引擎实现
    """

    def __init__(self, config: "WebSearchConfig | None" = None):
        super().__init__(config)

    def is_available(self) -> bool:
        """检查DuckDuckGo搜索引擎是否可用"""
        return True  # DuckDuckGo不需要API密钥，总是可用

    async def search(
        self,
        query: str,
        num_results: int = 3,
        time_range: str = "any"
    ) -> list[dict[str, Any]]:
        """执行DuckDuckGo搜索"""

        try:
            async with aDDGS() as ddgs:
                search_response = await ddgs.text(query, max_results=num_results)

            return [
                {"title": r.get("title"), "url": r.get("href"), "snippet": r.get("body"), "provider": "DuckDuckGo"}
                for r in search_response
            ]
        except Exception as e:
            logger.error(f"DuckDuckGo 搜索失败: {e}")
            return []
