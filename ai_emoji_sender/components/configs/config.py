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

    @config_section("selection")
    class SelectionSection(SectionBase):
        """表情包选择配置节"""

        emoji_count: int = Field(
            default=50,
            description="每次从数据库中随机抽取的表情包数量（建议 20-100）",
            ge=1,  # 至少 1 个
            le=200,  # 最多 200 个
        )
        
        model_task: str = Field(
            default="utils",
            description="使用的 LLM 模型任务类型（在 model.toml 中配置，如 chat、utils、thinking 等）",
        )
        
        enable_random_fallback: bool = Field(
            default=True,
            description="当 AI 选择失败时，是否随机选择一个表情包作为备选",
        )
        
        log_selection_detail: bool = Field(
            default=False,
            description="是否记录详细的 AI 选择过程（用于调试）",
        )

    @config_section("filter")
    class FilterSection(SectionBase):
        """表情包过滤配置节"""

        require_description: bool = Field(
            default=True,
            description="是否要求表情包必须有描述才能被选择",
        )
        
        min_description_length: int = Field(
            default=2,
            description="表情包描述的最小长度（字符数）",
            ge=0,
        )
        
        exclude_keywords: list[str] = Field(
            default_factory=list,
            description="排除包含这些关键词的表情包（例如：['广告', '二维码']）",
        )

    selection: SelectionSection = Field(
        default_factory=SelectionSection,
        description="表情包选择配置"
    )
    
    filter: FilterSection = Field(
        default_factory=FilterSection,
        description="表情包过滤配置"
    )
