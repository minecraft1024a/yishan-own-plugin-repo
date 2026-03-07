"""Web Search Tool Plugin 配置定义"""
from __future__ import annotations

from typing import ClassVar

from src.core.components.base.config import BaseConfig, Field, SectionBase, config_section


class WebSearchConfig(BaseConfig):
    """网络搜索工具插件配置"""

    config_name: ClassVar[str] = "config"
    config_description: ClassVar[str] = "网络搜索工具插件配置"

    @config_section("plugin")
    class PluginSection(SectionBase):
        """插件基本配置"""

        enabled: bool = Field(default=True, description="是否启用插件")
        version: str = Field(default="1.0.0", description="插件版本")

    @config_section("components")
    class ComponentsSection(SectionBase):
        """组件启用配置"""

        enable_web_search_tool: bool = Field(default=True, description="是否启用网络搜索工具")
        enable_web_search_service: bool = Field(default=True, description="是否启用网络搜索服务")

    @config_section("proxy")
    class ProxySection(SectionBase):
        """代理配置"""

        enable_proxy: bool = Field(default=False, description="是否启用代理")
        http_proxy: str | None = Field(
            default=None, description="HTTP代理地址，格式如: http://proxy.example.com:8080"
        )
        https_proxy: str | None = Field(
            default=None, description="HTTPS代理地址，格式如: http://proxy.example.com:8080"
        )
        socks5_proxy: str | None = Field(
            default=None, description="SOCKS5代理地址，格式如: socks5://proxy.example.com:1080"
        )

    @config_section("api_keys")
    class ApiKeysSection(SectionBase):
        """API密钥配置"""

        exa_api_key: str = Field(default="", description="Exa搜索引擎API密钥")
        tavily_api_key: str = Field(default="", description="Tavily搜索引擎API密钥")
        metaso_api_key: str = Field(default="", description="Metaso搜索引擎API密钥")
        serper_api_key: str = Field(default="", description="Serper搜索引擎API密钥")

    @config_section("search")
    class SearchSection(SectionBase):
        """搜索配置"""

        default_engine: str = Field(
            default="bing",
            description="默认搜索引擎 (exa/tavily/metaso/ddg/bing/searxng/serper)",
        )
        enabled_engines: list[str] = Field(
            default=["bing"],
            description="启用的搜索引擎列表",
        )
        search_strategy: str = Field(
            default="single",
            description="搜索策略：single(单引擎)/parallel(并行)/fallback(回退)",
        )
        max_results: int = Field(default=10, description="搜索返回的最大结果数")
        timeout: int = Field(default=30, description="搜索超时时间（秒）")

    @config_section("searxng")
    class SearXNGSection(SectionBase):
        """SearXNG搜索引擎配置"""

        base_url: str = Field(default="http://localhost:8080", description="SearXNG实例地址")

    @config_section("bing")
    class BingSection(SectionBase):
        """Bing搜索引擎配置"""

        fetch_page_content: bool = Field(
            default=True,
            description="是否抓取搜索结果页面的完整内容"
        )
        content_max_length: int = Field(
            default=3000,
            description="抓取的页面内容最大长度（字符数）"
        )
        max_concurrent_fetches: int = Field(
            default=3,
            description="并发抓取页面内容的最大数量"
        )
        abstract_max_length: int = Field(
            default=300,
            description="搜索结果摘要的最大长度（字符数）"
        )
        request_timeout: int = Field(
            default=10,
            description="请求超时时间（秒）"
        )
        content_fetch_timeout: int = Field(
            default=8,
            description="抓取页面内容的超时时间（秒）"
        )

    # 配置节实例
    plugin: PluginSection = Field(default_factory=PluginSection)
    components: ComponentsSection = Field(default_factory=ComponentsSection)
    proxy: ProxySection = Field(default_factory=ProxySection)
    api_keys: ApiKeysSection = Field(default_factory=ApiKeysSection)
    search: SearchSection = Field(default_factory=SearchSection)
    searxng: SearXNGSection = Field(default_factory=SearXNGSection)
    bing: BingSection = Field(default_factory=BingSection)
