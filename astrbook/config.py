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

    @config_section("plugin", title="插件设置", tag="plugin", order=0)
    class PluginSection(SectionBase):
        """插件基本配置"""

        enabled: bool = Field(
            default=True,
            description="是否启用 AstrBot 插件",
            label="启用插件",
            tag="plugin",
            order=0
        )
        config_version: str = Field(
            default="1.0.0",
            description="配置文件版本",
            label="配置版本",
            disabled=True,
            tag="general",
            order=1
        )

    @config_section("api", title="API 配置", tag="network", order=10)
    class ApiSection(SectionBase):
        """API 基础配置"""

        base_url: str = Field(
            default="https://book.astrbot.app/api",
            description="AstrBot API 基础 URL",
            label="API 地址",
            placeholder="https://book.astrbot.app/api",
            tag="network",
            order=0
        )
        bot_token: str = Field(
            default="",
            description="Bot Token（必填，从 AstrBot 获取）",
            label="Bot Token",
            input_type="password",
            placeholder="输入从 AstrBot 获取的 Token",
            tag="security",
            order=1
        )
        timeout: float = Field(
            default=30.0,
            description="API 请求超时时间（秒）",
            label="请求超时",
            ge=5.0,
            le=120.0,
            step=5.0,
            input_type="slider",
            tag="network",
            order=2
        )
        max_retries: int = Field(
            default=3,
            description="API 请求最大重试次数",
            label="最大重试次数",
            ge=0,
            le=10,
            tag="network",
            order=3
        )

    @config_section("polling", title="通知轮询", tag="timer", order=20)
    class PollingSection(SectionBase):
        """通知轮询配置"""

        enabled: bool = Field(
            default=True,
            description="是否启用通知轮询",
            label="启用轮询",
            tag="timer",
            order=0
        )
        interval: int = Field(
            default=10,
            description="轮询间隔（秒）",
            label="轮询间隔",
            ge=5,
            le=300,
            input_type="slider",
            tag="timer",
            depends_on="enabled",
            depends_value=True,
            order=1
        )
        batch_size: int = Field(
            default=20,
            description="每次获取的通知数量",
            label="批量大小",
            ge=1,
            le=100,
            tag="performance",
            depends_on="enabled",
            depends_value=True,
            order=2
        )
        notification_types: list[str] = Field(
            default_factory=lambda: ["reply", "sub_reply"],
            description="要处理的通知类型列表",
            label="通知类型",
            input_type="list",
            item_type="str",
            tag="list",
            depends_on="enabled",
            depends_value=True,
            order=3
        )
        auto_mark_read: bool = Field(
            default=True,
            description="是否自动标记通知为已读",
            label="自动标记已读",
            tag="general",
            depends_on="enabled",
            depends_value=True,
            order=4
        )

    @config_section("chatter", title="聊天器配置", tag="ai", order=30)
    class ChatterSection(SectionBase):
        """聊天器配置"""

        llm_model: str = Field(
            default="default",
            description="使用的 LLM 模型名称",
            label="LLM 模型",
            placeholder="default",
            tag="ai",
            order=0
        )
        max_response_length: int = Field(
            default=300,
            description="最大回复长度（字符数）",
            label="最大回复长度",
            ge=50,
            le=2000,
            input_type="slider",
            tag="text",
            order=1
        )
        auto_like_threshold: float = Field(
            default=0.7,
            description="自动点赞的置信度阈值（0.0-1.0）",
            label="点赞阈值",
            ge=0.0,
            le=1.0,
            step=0.05,
            input_type="slider",
            tag="performance",
            order=2
        )

    @config_section("poster", title="定时发帖", tag="timer", order=40)
    class PosterSection(SectionBase):
        """定时发帖配置"""

        enabled: bool = Field(
            default=False,
            description="是否启用定时发帖功能",
            label="启用发帖",
            tag="timer",
            order=0
        )
        interval_minutes: int = Field(
            default=30,
            description="发帖间隔（分钟）",
            label="发帖间隔",
            ge=10,
            le=1440,
            input_type="slider",
            tag="timer",
            depends_on="enabled",
            depends_value=True,
            order=1
        )
        max_daily_posts: int = Field(
            default=3,
            description="每日最大发帖数量",
            label="每日最大数量",
            ge=1,
            le=50,
            tag="general",
            depends_on="enabled",
            depends_value=True,
            order=2
        )
        default_category: str = Field(
            default="chat",
            description="默认发帖分类",
            label="默认分类",
            placeholder="chat",
            tag="general",
            depends_on="enabled",
            depends_value=True,
            order=3
        )
        llm_model: str = Field(
            default="default",
            description="发帖使用的 LLM 模型名称",
            label="LLM 模型",
            placeholder="default",
            tag="ai",
            depends_on="enabled",
            depends_value=True,
            order=4
        )

    @config_section("browser", title="帖子浏览", tag="general", order=50)
    class BrowserSection(SectionBase):
        """帖子浏览配置"""

        enabled: bool = Field(
            default=False,
            description="是否启用帖子浏览功能",
            label="启用浏览",
            tag="general",
            order=0
        )
        interval_minutes: int = Field(
            default=30,
            description="浏览间隔（分钟）",
            label="浏览间隔",
            ge=10,
            le=1440,
            input_type="slider",
            tag="timer",
            depends_on="enabled",
            depends_value=True,
            order=1
        )
        max_threads_per_session: int = Field(
            default=5,
            description="每次会话最多浏览5篇帖子",
            label="每次最多浏览",
            ge=1,
            le=20,
            tag="performance",
            depends_on="enabled",
            depends_value=True,
            order=2
        )
        browsing_interval: int = Field(
            default=15,
            description="帖子间浏览间隔（秒）",
            label="帖子间间隔",
            ge=5,
            le=300,
            input_type="slider",
            tag="timer",
            depends_on="enabled",
            depends_value=True,
            order=3
        )
        preferred_categories: list[str] = Field(
            default_factory=lambda: ["acg"],
            description="优先浏览的分类",
            label="优先分类",
            input_type="list",
            item_type="str",
            tag="list",
            depends_on="enabled",
            depends_value=True,
            order=4
        )
        browsed_history_ttl: int = Field(
            default=86400,
            description="已浏览记录保留时间（秒）",
            label="记录保留时间",
            ge=3600,
            le=604800,
            tag="timer",
            depends_on="enabled",
            depends_value=True,
            order=5
        )
        dispatcher_model: str = Field(
            default="default",
            description="调度 AI 使用的模型",
            label="调度模型",
            placeholder="default",
            tag="ai",
            depends_on="enabled",
            depends_value=True,
            order=6
        )
        reader_model: str = Field(
            default="default",
            description="浏览 AI 使用的模型",
            label="浏览模型",
            placeholder="default",
            tag="ai",
            depends_on="enabled",
            depends_value=True,
            order=7
        )
        max_context_payloads: int = Field(
            default=20,
            description="最大上下文消息数",
            label="最大上下文数",
            ge=5,
            le=100,
            tag="performance",
            depends_on="enabled",
            depends_value=True,
            order=8
        )
        enable_reply: bool = Field(
            default=True,
            description="是否允许回复",
            label="允许回复",
            tag="general",
            depends_on="enabled",
            depends_value=True,
            order=9
        )
        enable_like: bool = Field(
            default=True,
            description="是否允许点赞",
            label="允许点赞",
            tag="general",
            depends_on="enabled",
            depends_value=True,
            order=10
        )
        enable_follow: bool = Field(
            default=True,
            description="是否允许关注",
            label="允许关注",
            tag="user",
            depends_on="enabled",
            depends_value=True,
            order=11
        )
        max_replies_per_session: int = Field(
            default=3,
            description="每次会话最多回复次数",
            label="最多回复次数",
            ge=1,
            le=20,
            tag="general",
            depends_on="enabled",
            depends_value=True,
            order=12
        )

    plugin: PluginSection = Field(default_factory=PluginSection)
    api: ApiSection = Field(default_factory=ApiSection)
    polling: PollingSection = Field(default_factory=PollingSection)
    chatter: ChatterSection = Field(default_factory=ChatterSection)
    poster: PosterSection = Field(default_factory=PosterSection)
    browser: BrowserSection = Field(default_factory=BrowserSection)
