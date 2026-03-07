"""AstrBot 插件配置定义"""

from __future__ import annotations

from typing import ClassVar

from src.core.components.base.config import (
    BaseConfig,
    Field,
    SectionBase,
    config_section,
)


class AstrBotConfig(BaseConfig):
    """AstrBot 插件配置"""

    config_name: ClassVar[str] = "config"
    config_description: ClassVar[str] = "AstrBot 论坛集成插件配置"

    @config_section("plugin")
    class PluginSection(SectionBase):
        """插件基本配置"""

        enabled: bool = Field(default=True, description="是否启用 AstrBot 插件")
        config_version: str = Field(default="1.0.0", description="配置文件版本")

    @config_section("api")
    class ApiSection(SectionBase):
        """API 基础配置"""

        base_url: str = Field(
            default="https://book.astrbot.app/api",
            description="AstrBot API 基础 URL",
        )
        bot_token: str = Field(
            default="", description="Bot Token（必填，从 AstrBot 获取）"
        )
        timeout: float = Field(default=30.0, description="API 请求超时时间（秒）")
        max_retries: int = Field(default=3, description="API 请求最大重试次数")

    @config_section("polling")
    class PollingSection(SectionBase):
        """通知轮询配置"""

        enabled: bool = Field(default=True, description="是否启用通知轮询")
        interval: int = Field(default=10, description="轮询间隔（秒）")
        batch_size: int = Field(default=20, description="每次获取的通知数量")
        notification_types: list[str] = Field(
            default_factory=lambda: ["reply", "sub_reply"],
            description="要处理的通知类型列表",
        )
        auto_mark_read: bool = Field(default=True, description="是否自动标记通知为已读")

    @config_section("chatter")
    class ChatterSection(SectionBase):
        """聊天器配置"""

        llm_model: str = Field(default="default", description="使用的 LLM 模型名称")
        max_response_length: int = Field(
            default=300, description="最大回复长度（字符数）"
        )
        auto_like_threshold: float = Field(
            default=0.7,
            description="自动点赞的置信度阈值（0.0-1.0）",
        )

    @config_section("poster")
    class PosterSection(SectionBase):
        """定时发帖配置"""

        enabled: bool = Field(default=False, description="是否启用定时发帖功能")
        interval_minutes: int = Field(default=30, description="发帖间隔（分钟）")
        max_daily_posts: int = Field(default=3, description="每日最大发帖数量")
        default_category: str = Field(default="chat", description="默认发帖分类")
        llm_model: str = Field(default="default", description="发帖使用的 LLM 模型名称")

    @config_section("browser")
    class BrowserSection(SectionBase):
        """帖子浏览配置"""

        enabled: bool = Field(default=False, description="是否启用帖子浏览功能")
        interval_minutes: int = Field(default=30, description="浏览间隔（分钟）")
        max_threads_per_session: int = Field(
            default=5, description="每次会话最多浏览5篇帖子"
        )
        browsing_interval: int = Field(default=15, description="帖子间浏览间隔（秒）")
        preferred_categories: list[str] = Field(
            default_factory=lambda: ["acg"],
            description="优先浏览的分类",
        )
        browsed_history_ttl: int = Field(
            default=86400, description="已浏览记录保留时间（秒）"
        )
        dispatcher_model: str = Field(
            default="default", description="调度 AI 使用的模型"
        )
        reader_model: str = Field(default="default", description="浏览 AI 使用的模型")
        max_context_payloads: int = Field(default=20, description="最大上下文消息数")
        enable_reply: bool = Field(default=True, description="是否允许回复")
        enable_like: bool = Field(default=True, description="是否允许点赞")
        enable_follow: bool = Field(default=True, description="是否允许关注")
        max_replies_per_session: int = Field(
            default=3, description="每次会话最多回复次数"
        )

    plugin: PluginSection = Field(default_factory=PluginSection)
    api: ApiSection = Field(default_factory=ApiSection)
    polling: PollingSection = Field(default_factory=PollingSection)
    chatter: ChatterSection = Field(default_factory=ChatterSection)
    poster: PosterSection = Field(default_factory=PosterSection)
    browser: BrowserSection = Field(default_factory=BrowserSection)
