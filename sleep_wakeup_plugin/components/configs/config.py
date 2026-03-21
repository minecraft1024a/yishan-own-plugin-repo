"""sleep_wakeup_plugin 配置定义。"""

from typing import ClassVar

from src.core.components.base import BaseConfig
from src.kernel.config.core import Field, SectionBase, config_section


class Config(BaseConfig):
    """睡眠/苏醒插件配置。"""

    config_name: ClassVar[str] = "config"
    config_description: ClassVar[str] = "睡眠/苏醒离散状态机插件配置"

    @config_section("general", title="通用设置", tag="general", order=0)
    class GeneralSection(SectionBase):
        """通用设置。"""

        enabled: bool = Field(
            default=True,
            description="是否启用 sleep_wakeup_plugin",
            label="启用插件",
            order=0,
        )
        debug_mode: bool = Field(
            default=False,
            description="是否输出调试日志",
            label="调试模式",
            order=1,
        )

    @config_section("timing", title="时间参数", tag="timer", order=10)
    class TimingSection(SectionBase):
        """时间参数设置。"""

        sleep_target_time: str = Field(
            default="23:30",
            description="预计入睡时间点（HH:MM）",
            label="入睡时间点",
            order=0,
        )
        wake_target_time: str = Field(
            default="07:30",
            description="预计苏醒时间点（HH:MM）",
            label="苏醒时间点",
            order=1,
        )
        sleep_window_minutes: int = Field(
            default=90,
            ge=1,
            le=720,
            description="入睡窗口（分钟），定义预计入睡阶段长度",
            label="入睡窗口(分钟)",
            order=2,
        )
        wake_window_minutes: int = Field(
            default=120,
            ge=1,
            le=720,
            description="苏醒窗口（分钟），定义预计苏醒阶段长度",
            label="苏醒窗口(分钟)",
            order=3,
        )
        update_interval_seconds: int = Field(
            default=30,
            ge=10,
            le=3600,
            description="困倦值更新周期（秒）",
            label="更新周期(秒)",
            order=4,
        )

    @config_section("model", title="状态机参数", tag="model", order=20)
    class ModelSection(SectionBase):
        """状态机参数。"""

        guardian_model_task: str = Field(
            default="actor",
            description="守护决策使用的模型任务名",
            label="守护模型任务",
            order=0,
        )
        guardian_timeout_seconds: int = Field(
            default=20,
            ge=5,
            le=120,
            description="守护决策调用大模型的超时时间（秒）",
            label="守护超时(秒)",
            order=1,
        )

        pre_sleep_step: int = Field(
            default=2,
            ge=1,
            le=30,
            description="预计入睡阶段每次更新增加的困倦值",
            label="入睡阶段增量",
            order=2,
        )
        sleep_phase_step: int = Field(
            default=6,
            ge=1,
            le=50,
            description="预计睡眠阶段每次更新增加的困倦值",
            label="睡眠阶段增量",
            order=3,
        )
        pre_wake_step: int = Field(
            default=3,
            ge=1,
            le=30,
            description="预计苏醒阶段每次更新降低的困倦值",
            label="苏醒阶段减量",
            order=4,
        )
        lie_in_reset_drowsiness: int = Field(
            default=10,
            ge=1,
            le=99,
            description="守护驳回苏醒时重置的困倦值",
            label="赖床重置困倦值",
            order=5,
        )
        max_lie_in_attempts: int = Field(
            default=1,
            ge=0,
            le=10,
            description="守护驳回最大次数，超过后强制批准苏醒",
            label="最大赖床次数",
            order=6,
        )

    @config_section("guard", title="消息拦截", tag="guard", order=30)
    class GuardSection(SectionBase):
        """守护消息拦截设置。"""

        block_messages_when_sleeping: bool = Field(
            default=True,
            description="角色处于 sleeping 时是否阻挡消息事件",
            label="睡眠期阻挡消息",
            order=0,
        )
        enable_private_message_wakeup: bool = Field(
            default=True,
            description="检测到私聊消息时是否降低困倦值",
            label="私聊触发唤醒",
            order=1,
        )
        private_message_wakeup_delta: int = Field(
            default=12,
            ge=1,
            le=100,
            description="每次检测到私聊消息时降低的困倦值",
            label="私聊唤醒降幅",
            order=2,
        )
        wakeup_user_list_type: str = Field(
            default="all",
            description="私聊唤醒用户名单模式: whitelist=白名单, blacklist=黑名单, all=允许所有",
            label="唤醒名单模式",
            input_type="select",
            choices=["whitelist", "blacklist", "all"],
            order=3,
        )
        wakeup_user_list: list[str] = Field(
            default_factory=list,
            description="私聊唤醒用户列表（格式：platform:user_id，如 qq:123456789）",
            label="唤醒用户列表",
            input_type="list",
            item_type="str",
            order=4,
        )

    @config_section("storage", title="持久化", tag="storage", order=40)
    class StorageSection(SectionBase):
        """持久化设置。"""

        state_key: str = Field(
            default="runtime_state",
            description="JSON 存储键名",
            label="状态键名",
            order=0,
        )
        max_history_records: int = Field(
            default=500,
            ge=50,
            le=5000,
            description="保留的最大历史记录数量",
            label="历史记录上限",
            order=1,
        )

    general: GeneralSection = Field(default_factory=GeneralSection)
    timing: TimingSection = Field(default_factory=TimingSection)
    model: ModelSection = Field(default_factory=ModelSection)
    guard: GuardSection = Field(default_factory=GuardSection)
    storage: StorageSection = Field(default_factory=StorageSection)
