"""LLM 分段提示词注入器。

当 general.segment_mode == "llm" 时，订阅 on_prompt_build 事件，
向指定 LLM 提示词模板注入分段指令，告知 LLM 在合适位置插入分段标记。

Created by: minecraft1024a
"""

from __future__ import annotations

from typing import Any, cast

from src.app.plugin_system.api.log_api import get_logger
from src.core.components.base import BaseEventHandler
from src.core.prompt.template import PROMPT_BUILD_EVENT
from src.kernel.event import EventDecision

from message_process_plugin.components.configs.config import Config

logger = get_logger(__name__)

# 内置默认分段指令，当用户在配置文件中留空时使用
_DEFAULT_SEGMENT_INSTRUCTION = (
    "## 消息分段发送\n"
    "你可以像在 QQ、微信聊天一样把回复拆成多条消息分开发送。\n"
    "在需要分段的位置插入标记 `{marker}`，系统会自动将其拆分成多条依次发出。\n\n"
    "**分段规则**：\n"
    "- 分段标记本身承担标点的停顿功能，**标记前不要加任何标点符号**；\n"
    "- 在话题转换、情绪切换、一问一答等自然停顿处分段；\n"
    "- 每段保持语义完整，不要在一句话中途断开；\n"
    "- 内容简短或只有一句话时不必分段；\n"
    "- 每次回复最多分 3～4 段，避免刷屏。"
)


class LLMSegmentInjector(BaseEventHandler):
    """LLM 分段提示词注入器。

    在 on_prompt_build 事件触发时，若当前分段模式为 ``llm``，
    则向配置的目标提示词模板中追加分段指令，指示 LLM 在希望
    分段处插入 ``split_marker``，供 ``SegmentSenderEvent`` 拦截处理。

    Attributes:
        handler_name: 处理器名称
        handler_description: 处理器描述
        weight: 执行优先级
        intercept_message: 是否拦截消息（否）
        init_subscribe: 初始订阅事件列表
    """

    handler_name: str = "llm_segment_injector"
    handler_description: str = "向 LLM 提示词注入分段指令（LLM 分段模式）"
    weight: int = 10
    intercept_message: bool = False
    init_subscribe: list[str] = [PROMPT_BUILD_EVENT]

    async def execute(
        self, event_name: str, params: dict[str, Any]
    ) -> tuple[EventDecision, dict[str, Any]]:
        """处理 on_prompt_build 事件，按需注入分段指令。

        Args:
            event_name: 事件名称
            params: 事件参数，含 name / template / values 字段

        Returns:
            tuple[EventDecision, dict[str, Any]]: 决策与（可能已修改的）参数
        """
        config = self._get_config()
        if config is None:
            return EventDecision.PASS, params

        if config.general.segment_mode != "llm":
            return EventDecision.PASS, params

        prompt_name: str = params.get("name", "")
        if prompt_name not in config.llm_segment.inject_prompt_names:
            return EventDecision.PASS, params

        marker = config.llm_segment.split_marker
        raw_instruction = config.llm_segment.segment_instruction.strip()
        instruction_template = raw_instruction if raw_instruction else _DEFAULT_SEGMENT_INSTRUCTION
        instruction = instruction_template.replace("{marker}", marker)

        # default_chatter_user_prompt 使用 values["extra"] 注入
        if prompt_name == "default_chatter_user_prompt":
            values: dict[str, Any] = params.get("values", {})
            existing_extra: str = values.get("extra", "") or ""
            sep = "\n\n" if existing_extra else ""
            values["extra"] = existing_extra + sep + instruction
            params["values"] = values
            if config.general.debug_mode:
                logger.debug(f"已向 {prompt_name} 注入 LLM 分段指令（via extra）")

        # kfc_system_prompt 及其他模板直接追加到 template 末尾
        else:
            template: str = params.get("template", "")
            params["template"] = template + "\n\n" + instruction
            if config.general.debug_mode:
                logger.debug(f"已向 {prompt_name} 注入 LLM 分段指令（via template append）")

        return EventDecision.SUCCESS, params

    def _get_config(self) -> Config | None:
        """获取插件配置实例。

        Returns:
            Config 实例，若无法获取则返回 None
        """
        if not self.plugin or not self.plugin.config:
            return None
        return cast(Config, self.plugin.config)
