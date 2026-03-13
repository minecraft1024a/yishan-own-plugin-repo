"""
消息分段发送插件配置

Created by: minecraft1024a
Created at: 2026-02-24
"""

from typing import ClassVar

from src.core.components.base import BaseConfig
from src.kernel.config.core import Field, SectionBase, config_section


class Config(BaseConfig):
    """消息分段发送插件配置。

    Config 组件用于管理插件配置。
    """

    config_name: ClassVar[str] = "config"
    config_description: ClassVar[str] = "消息分段发送插件配置"

    @config_section("general", title="通用设置", tag="general", order=0)
    class GeneralSection(SectionBase):
        """通用配置节"""

        enabled: bool = Field(
            default=True,
            description="是否启用分段发送功能",
            label="启用插件",
            tag="general",
            order=0
        )
        debug_mode: bool = Field(
            default=False,
            description="调试模式（打印详细分段日志）",
            label="调试模式",
            tag="debug",
            hint="开启后会在日志中打印详细的分段信息",
            order=1
        )

    @config_section("segment", title="分段规则", tag="text", order=10)
    class SegmentSection(SectionBase):
        """分段规则配置节"""

        punctuation: str = Field(
            default=r"[。！？；,，.!?;]\s*",
            description="分段标点符号正则表达式（中英文），仅在 _should_handle 判断时使用",
            label="标点符号正则",
            input_type="text",
            tag="text",
            hint="用于识别句子分隔的正则表达式",
            order=0
        )
        min_segments: int = Field(
            default=2,
            description="最小分段数量（少于此值不分段直接发送）",
            label="最小分段数",
            ge=1,
            le=10,
            tag="text",
            order=1
        )
        max_segments: int = Field(
            default=4,
            description="最大分段数量（超过后智能合并最短相邻段）",
            label="最大分段数",
            ge=1,
            le=20,
            tag="text",
            order=2
        )
        preserve_punctuation: bool = Field(
            default=True,
            description="是否保留标点符号在句末",
            label="保留标点",
            tag="text",
            order=4
        )
        enable_merge: bool = Field(
            default=True,
            description="是否启用概率合并（相邻短句在弱标点处概率性合并）",
            label="启用概率合并",
            tag="text",
            order=5
        )
        base_split_strength: float = Field(
            default=-1.0,
            description="基础分割强度 (0.0~1.0)，-1 表示按文本长度自动调整",
            label="分割强度",
            ge=-1.0,
            le=1.0,
            step=0.1,
            tag="performance",
            hint="-1 表示自动调整",
            order=6
        )

    @config_section("protection", title="内容保护", tag="text", order=20)
    class ProtectionSection(SectionBase):
        """内容保护配置节"""

        enable_kaomoji: bool = Field(
            default=True,
            description="是否保护颜文字不被分割",
            label="保护颜文字",
            tag="text",
            order=0
        )
        enable_quote: bool = Field(
            default=True,
            description="是否保护引号包裹的内容不被分割",
            label="保护引号内容",
            tag="text",
            order=1
        )
        enable_code_block: bool = Field(
            default=True,
            description="是否保护代码块和数学公式不被分割",
            label="保护代码块",
            tag="text",
            order=2
        )
        enable_url: bool = Field(
            default=True,
            description="是否保护 URL 不被分割",
            label="保护 URL",
            tag="network",
            order=3
        )
        enable_pair: bool = Field(
            default=True,
            description="是否保护成对括号内容不被分割",
            label="保护括号内容",
            tag="text",
            order=4
        )

    @config_section("skipping", title="跳过规则", tag="list", order=30)
    class SkippingSection(SectionBase):
        """跳过规则配置节"""

        skip_message_id_prefixes: list[str] = Field(
            default=["action_kfc_reply_","api_"],
            description=(
                "message_id 前缀白名单：以列表中任意前缀开头的消息会被跳过分段。"
                "用于声明「已自行管理分段节奏」的 action，"
                "例如 KokroFlowChatter 的 kfc_reply。"
                "每个 action 的 message_id 格式为 action_<action_name>_<uuid>。"
            ),
            label="跳过的消息前缀",
            input_type="list",
            item_type="str",
            tag="list",
            hint="以这些前缀开头的消息不会被分段",
            order=0
        )

    @config_section("sending", title="发送行为", tag="performance", order=40)
    class SendingSection(SectionBase):
        """发送行为配置节"""

        delay_between_segments: float = Field(
            default=0.0,
            description="分段之间的固定发送延迟（秒），叠加在打字延迟之后",
            label="分段间延迟",
            ge=0.0,
            le=10.0,
            step=0.1,
            input_type="slider",
            tag="timer",
            hint="额外的固定延迟时间",
            order=0
        )
        typing_speed_cps: float = Field(
            default=8.0,
            description=(
                "模拟打字速度（字符/秒）。"
                "发送每段前按 len(段) / typing_speed_cps 计算延迟以模拟打字效果。"
                "设为 0 禁用动态打字延迟。"
            ),
            label="打字速度",
            ge=0.0,
            le=50.0,
            step=0.5,
            input_type="slider",
            tag="performance",
            hint="0 表示禁用打字延迟",
            order=1
        )
        min_typing_delay: float = Field(
            default=0.5,
            description="单段打字延迟的最小值（秒）",
            label="最小打字延迟",
            ge=0.0,
            le=5.0,
            step=0.1,
            tag="timer",
            order=2
        )
        max_typing_delay: float = Field(
            default=6.0,
            description="单段打字延迟的最大值（秒）",
            label="最大打字延迟",
            ge=0.0,
            le=30.0,
            step=0.5,
            tag="timer",
            order=3
        )
        fail_strategy: str = Field(
            default="continue",
            description="某段发送失败时的策略：continue（继续发送）/ stop（停止发送）",
            label="失败策略",
            input_type="select",
            choices=["continue", "stop"],
            tag="general",
            order=4
        )
        log_progress: bool = Field(
            default=True,
            description="是否记录分段发送进度",
            label="记录发送进度",
            tag="debug",
            order=5
        )

    # 配置节实例
    general: GeneralSection = Field(default_factory=GeneralSection)
    segment: SegmentSection = Field(default_factory=SegmentSection)
    protection: ProtectionSection = Field(default_factory=ProtectionSection)
    skipping: SkippingSection = Field(default_factory=SkippingSection)
    sending: SendingSection = Field(default_factory=SendingSection)
