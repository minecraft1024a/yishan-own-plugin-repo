"""AI 表情包选择器插件配置

用户可配置项：
- 一次性抽取的表情包数量
- 使用的 AI 模型任务类型
"""

from typing import ClassVar

from src.core.components.base import BaseConfig
from src.kernel.config.core import Field, SectionBase, config_section


class Config(BaseConfig):
    """AI 表情包选择器插件配置。

    管理插件的所有可配置项。
    """

    config_name: ClassVar[str] = "config"
    config_description: ClassVar[str] = "AI 表情包选择器插件配置"

    @config_section("selection", title="选择配置", tag="ai", order=0)
    class SelectionSection(SectionBase):
        """表情包选择配置节"""

        emoji_count: int = Field(
            default=50,
            description="每次从数据库中随机抽取的表情包数量（建议 20-100）",
            label="抽取数量",
            ge=1,
            le=200,
            input_type="slider",
            tag="general",
            hint="建议 20-100 之间",
            order=0
        )
        
        model_task: str = Field(
            default="utils",
            description="使用的 LLM 模型任务类型（在 model.toml 中配置，如 chat、utils、thinking 等）",
            label="模型任务",
            placeholder="utils",
            tag="ai",
            hint="确保此任务在 model.toml 中已配置",
            order=1
        )
        
        enable_random_fallback: bool = Field(
            default=True,
            description="当 AI 选择失败时，是否随机选择一个表情包作为备选",
            label="启用随机备选",
            tag="general",
            order=2
        )
        
        log_selection_detail: bool = Field(
            default=False,
            description="是否记录详细的 AI 选择过程（用于调试）",
            label="记录选择详情",
            tag="debug",
            order=3
        )

    @config_section("filter", title="过滤配置", tag="list", order=10)
    class FilterSection(SectionBase):
        """表情包过滤配置节"""

        require_description: bool = Field(
            default=True,
            description="是否要求表情包必须有描述才能被选择",
            label="要求有描述",
            tag="general",
            order=0
        )
        
        min_description_length: int = Field(
            default=2,
            description="表情包描述的最小长度（字符数）",
            label="描述最小长度",
            ge=0,
            le=100,
            tag="text",
            order=1
        )
        
        exclude_keywords: list[str] = Field(
            default_factory=list,
            description="排除包含这些关键词的表情包（例如：['广告', '二维码']）",
            label="排除关键词",
            input_type="list",
            item_type="str",
            tag="list",
            hint="表情包描述中包含这些词的将被排除",
            order=2
        )

    selection: SelectionSection = Field(
        default_factory=SelectionSection,
        description="表情包选择配置"
    )
    
    filter: FilterSection = Field(
        default_factory=FilterSection,
        description="表情包过滤配置"
    )
