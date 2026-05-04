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

    @config_section("plugin", title="插件设置", tag="plugin")
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

    @config_section("api", title="API 配置", tag="network")
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

    @config_section("polling", title="通知轮询", tag="timer")
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

    @config_section("chatter", title="聊天器配置", tag="ai")
    class ChatterSection(SectionBase):
        """聊天器配置"""

        llm_model: str = Field(
            default="actor",
            description="使用的 LLM 模型名称",
            label="LLM 模型",
            placeholder="actor",
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

    @config_section("agent", title="社区 Agent 配置", tag="agent")
    class AgentSection(SectionBase):
        """社区活动 Agent 配置（替代 poster + browser）"""

        enabled: bool = Field(
            default=True,
            description="是否启用社区活动 Agent",
            label="启用 Agent",
            tag="agent",
            order=0
        )

        # === 调度配置 ===
        interval_enabled: bool = Field(
            default=False,
            description="是否定时触发社区活动 Agent",
            label="定时触发 Agent",
            tag="agent",
            order=0
        )

        interval_minutes: int = Field(
            default=30,
            ge=5,
            le=1440,
            description="Agent 触发间隔（分钟）",
            label="触发间隔",
            tag="timer",
            order=1
        )

        # === 决策配置 ===
        llm_model: str = Field(
            default="actor",
            description="Agent 决策使用的 LLM 模型（任务名称）",
            label="决策模型",
            tag="ai",
            order=2
        )

        max_decision_rounds: int = Field(
            default=10,
            ge=3,
            le=30,
            description="单次任务最多决策轮数",
            label="最大决策轮数",
            tag="performance",
            order=3
        )

        decision_timeout: int = Field(
            default=300,
            ge=60,
            le=600,
            description="单次任务超时时间（秒）",
            label="任务超时",
            tag="performance",
            order=4
        )

        # === 行为配额 ===
        max_posts_per_day: int = Field(
            default=3,
            ge=1,
            le=20,
            description="每日最大发帖数",
            label="每日发帖上限",
            tag="quota",
            order=5
        )

        max_replies_per_day: int = Field(
            default=10,
            ge=1,
            le=50,
            description="每日最大回复数",
            label="每日回复上限",
            tag="quota",
            order=6
        )

        max_likes_per_day: int = Field(
            default=20,
            ge=1,
            le=100,
            description="每日最大点赞数",
            label="每日点赞上限",
            tag="quota",
            order=7
        )

        max_reads_per_session: int = Field(
            default=5,
            ge=1,
            le=20,
            description="单次最多阅读帖子数",
            label="单次阅读上限",
            tag="performance",
            order=8
        )

        # === 发帖配置 ===
        post_default_category: str = Field(
            default="chat",
            description="发帖默认分类",
            label="默认分类",
            tag="post",
            order=9
        )

        post_use_search: bool = Field(
            default=False,
            description="发帖时是否调用搜索服务获取灵感",
            label="使用搜索服务",
            tag="post",
            order=10
        )

        post_llm_model: str = Field(
            default="actor",
            description="发帖内容生成使用的 LLM 模型",
            label="发帖模型",
            tag="ai",
            order=11
        )

        # === 状态管理 ===
        state_ttl_days: int = Field(
            default=7,
            ge=1,
            le=30,
            description="状态记录保留天数",
            label="状态保留天数",
            tag="storage",
            order=17
        )

    plugin: PluginSection = Field(default_factory=PluginSection)
    api: ApiSection = Field(default_factory=ApiSection)
    polling: PollingSection = Field(default_factory=PollingSection)
    chatter: ChatterSection = Field(default_factory=ChatterSection)
    agent: AgentSection = Field(default_factory=AgentSection)
