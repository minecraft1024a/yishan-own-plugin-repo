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

    @config_section("general", title="通用设置", tag="general")
    class GeneralSection(SectionBase):
        """通用配置节"""

        enabled: bool = Field(
            default=True,
            description="是否启用分段发送功能",
            label="启用插件",
            tag="general",
            order=0
        )
        segment_mode: str = Field(
            default="punctuation",
            description="分段模式：punctuation（标点分段）/ llm（让 LLM 自行决定分段位置）",
            label="分段模式",
            input_type="select",
            choices=["punctuation", "llm"],
            tag="general",
            hint="llm 模式下，LLM 会在希望分段处插入标记，插件拦截后按标记拆分发送",
            order=1
        )
        debug_mode: bool = Field(
            default=False,
            description="调试模式（打印详细分段日志）",
            label="调试模式",
            tag="debug",
            hint="开启后会在日志中打印详细的分段信息",
            order=2
        )

    @config_section("segment", title="分段规则", tag="text")
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
        separators: list[str] = Field(
            default=["，", ",", " ", "。", ";", "∽", "≈", "~", "～", "…", "！", "!", "？", "?"],
            description="分割点字符列表，文本在这些字符处被切分成段",
            label="分割字符",
            input_type="list",
            item_type="str",
            tag="text",
            order=7
        )
        strong_separators: list[str] = Field(
            default=["∽", "≈", "~", "～", "…", "！", "!", "？", "?"],
            description="强语义分隔符列表，匹配的字符在分段后保留在句尾而不被去掉",
            label="强语义分隔符",
            input_type="list",
            item_type="str",
            tag="text",
            order=8
        )

    @config_section("protection", title="内容保护", tag="text")
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

    @config_section("skipping", title="跳过规则", tag="list")
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

    @config_section("sending", title="发送行为", tag="performance")
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

    @config_section("llm_segment", title="LLM 分段设置", tag="llm")
    class LLMSegmentSection(SectionBase):
        """LLM 分段模式配置节。

        当 general.segment_mode == "llm" 时生效。
        插件会向 LLM 提示词中注入分段指令，
        LLM 在希望分段的位置插入 split_marker，
        插件拦截后按标记拆分并逐段发送。
        """

        split_marker: str = Field(
            default="[分段]",
            description="LLM 在分段处插入的标记文本，插件据此拆分消息",
            label="分段标记",
            tag="llm",
            hint="该标记应足够独特，避免与正常回复内容冲突",
            order=0,
        )
        inject_prompt_names: list[str] = Field(
            default=["default_chatter_user_prompt"],
            description="向哪些提示词模板注入分段指令（填写 on_prompt_build 事件中的模板 name）",
            label="注入目标模板",
            input_type="list",
            item_type="str",
            tag="llm",
            hint="不同 chatter 使用的模板名不同，请根据实际插件配置填写",
            order=1,
        )
        segment_instruction: str = Field(
            default="",
            description=(
                "注入到提示词中的分段指令模板，{marker} 会被替换为实际的分段标记。"
                "留空则使用内置默认指令。支持 Markdown 格式。"
            ),
            label="分段指令模板",
            input_type="textarea",
            tag="llm",
            hint="留空时自动使用内置默认指令",
            order=2,
        )

    # 配置节实例
    general: GeneralSection = Field(default_factory=GeneralSection)
    segment: SegmentSection = Field(default_factory=SegmentSection)
    protection: ProtectionSection = Field(default_factory=ProtectionSection)
    skipping: SkippingSection = Field(default_factory=SkippingSection)
    sending: SendingSection = Field(default_factory=SendingSection)
    llm_segment: LLMSegmentSection = Field(default_factory=LLMSegmentSection)
