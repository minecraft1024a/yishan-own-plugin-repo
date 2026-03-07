"""
Base search engine interface
"""

from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import WebSearchConfig


class BaseSearchEngine(ABC):
    """
    搜索引擎基类
    """

    def __init__(self, config: "WebSearchConfig | None" = None):
        """
        初始化搜索引擎

        Args:
            config: 插件配置对象（可选）
        """
        self.config = config

    @abstractmethod
    async def search(
        self,
        query: str,
        num_results: int = 3,
        time_range: str = "any"
    ) -> list[dict[str, Any]]:
        """
        执行搜索

        Args:
            query: 搜索查询关键词
            num_results: 返回结果数量，默认为3
            time_range: 时间范围，可选值："any", "week", "month"，默认为"any"

        Returns:
            搜索结果列表，每个结果包含 title、url、snippet、provider 字段
        """
        pass

    async def read_url(self, url: str) -> str | None:
        """
        读取URL内容，如果引擎不支持则返回None
        """
        return None

    @abstractmethod
    def is_available(self) -> bool:
        """
        检查搜索引擎是否可用
        """
        pass
