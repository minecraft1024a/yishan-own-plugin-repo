"""配置系统

基于 Neo-MoFox 的配置框架。
"""

from typing import ClassVar

from src.core.components.base.config import (
    BaseConfig,
    Field,
    SectionBase,
    config_section,
)


class ScheduleConfig(BaseConfig):
    """日程表系统配置"""

    config_name: ClassVar[str] = "config"
    config_description: ClassVar[str] = "日程表系统配置"

    @config_section("schedule")
    class ScheduleSection(SectionBase):
        """日程表配置节"""

        enabled: bool = Field(True, description="是否启用日程表功能")
        generation_model: str = Field(
            "actor", description="日程生成使用的模型任务名"
        )
        generation_timeout: int = Field(300, description="生成超时时间（秒）")
        max_retries: int = Field(3, description="生成失败最大重试次数")
        retry_delay: int = Field(5, description="重试延迟（秒）")
        generation_time: str = Field("23:00", description="每日生成时间 (HH:MM)")
        custom_guidelines: str = Field("", description="自定义生成指南")

    @config_section("plan")
    class PlanSection(SectionBase):
        """月度计划配置节"""

        enabled: bool = Field(True, description="是否启用月度计划功能")
        max_plans_per_month: int = Field(15, description="每月最大计划数")
        completion_threshold: int = Field(
            3, description="自动完成阈值（使用N次后自动标记为完成）"
        )
        avoid_repetition_days: int = Field(
            7, description="避免重复的天数（N天内不重复相似计划）"
        )

    schedule: ScheduleSection = Field(default_factory=ScheduleSection)
    plan: PlanSection = Field(default_factory=PlanSection)
