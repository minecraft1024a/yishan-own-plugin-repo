"""
消息分段发送事件处理器

监听 ON_MESSAGE_SENT 事件，在消息实际发出前拦截文本消息，
按智能分割逻辑将其拆成多段后逐句发送，模拟自然打字节奏。

Created by: minecraft1024a
Created at: 2026-02-24
"""

import asyncio
from typing import Any, cast

from src.app.plugin_system.api.log_api import get_logger
from src.app.plugin_system.api.send_api import send_text
from src.core.components.base import BaseEventHandler
from src.core.components.types import EventType
from src.core.models.message import Message, MessageType
from src.kernel.event import EventDecision

from message_process_plugin.components.configs.config import Config
from message_process_plugin.utils import split_into_sentences

logger = get_logger(__name__)


class SegmentSenderEvent(BaseEventHandler):
    """消息分段发送事件处理器。

    在消息发送前拦截文本消息，通过智能分割逻辑将其拆成多段后逐句发送，
    模拟自然打字节奏，提升对话体验。

    功能特性：
    - 监听 ON_MESSAGE_SENT 事件（消息实际发出之前）
    - 仅处理文本类型消息
    - 多层内容保护（颜文字、引号、代码块、URL、括号）不被错误分割
    - 弱标点处概率性合并，强标点处稳定分割
    - 支持 message_id 前缀白名单，跳过已自行管理分段节奏的 action
    - 模拟打字延迟，发送间隔更自然
    """

    handler_name = "segment_sender_event"
    handler_description = "消息分段发送事件处理器 - 根据标点符号分段逐句发送"
    weight = 100          # 权重较高，优先于其他处理器执行
    intercept_message = True
    init_subscribe = [EventType.ON_MESSAGE_SENT]

    async def execute(
        self, event_name: str, params: dict[str, Any]
    ) -> tuple[EventDecision, dict[str, Any]]:
        """处理发送事件，将消息分段逐句发送。

        Args:
            event_name: 触发本处理器的事件名称
            params: 事件参数字典，包含：
                - message: Message 对象（待发送的消息）
                - envelope: MessageEnvelope 对象
                - adapter_signature: 适配器签名

        Returns:
            tuple[EventDecision, dict[str, Any]]:
                - (STOP, params)   — 成功分段发送，拦截原始消息
                - (SUCCESS, params) — 无需分段或分段失败，放行原始消息
        """
        try:
            config = self._get_config()
            if config is None or not config.general.enabled:
                if config and config.general.debug_mode:
                    logger.debug("分段发送功能已禁用，放行原始消息")
                return EventDecision.SUCCESS, params

            message: Message | None = params.get("message")  # type: ignore
            if message is None:
                logger.warning("事件参数中缺少 message，放行原始消息")
                return EventDecision.SUCCESS, params

            # 仅检查消息类型和基本内容
            if message.message_type != MessageType.TEXT:
                return EventDecision.SUCCESS, params
                
            content = message.content
            if not content or not isinstance(content, str) or not content.strip():
                return EventDecision.SUCCESS, params

            # 白名单前缀检查：跳过已自行管理分段节奏的 action / 通过sendapi发送的分段消息
            msg_id = str(message.message_id or "")
            for prefix in config.skipping.skip_message_id_prefixes:
                if msg_id.startswith(prefix):
                    if config.general.debug_mode:
                        logger.debug(f"跳过白名单前缀消息: message_id={msg_id}, prefix={prefix}")
                    return EventDecision.SUCCESS, params

            # 直接尝试分段
            content_str = str(content)
            prot = config.protection
            seg = config.segment
            
            sentences = split_into_sentences(
                text=content_str,
                base_split_strength=seg.base_split_strength,
                enable_merge=seg.enable_merge,
                max_segments=seg.max_segments,
                enable_kaomoji=prot.enable_kaomoji,
                enable_quote=prot.enable_quote,
                enable_code_block=prot.enable_code_block,
                enable_url=prot.enable_url,
                enable_pair=prot.enable_pair,
            )

            # 判断是否需要分段（少于 min_segments 就放行原消息）
            if not sentences or len(sentences) < seg.min_segments:
                if config.general.debug_mode:
                    logger.debug(
                        f"分段数量不足 ({len(sentences) if sentences else 0} < {seg.min_segments})，放行原始消息"
                    )
                return EventDecision.SUCCESS, params

            # 执行分段发送
            await self._send_segments(message, sentences, config)

            if config.sending.log_progress:
                logger.info(f"消息分段发送完成: message_id={message.message_id}")

            # 拦截原始消息，由本处理器接管发送
            continue_send = params.get("continue_send", False)
            if continue_send:
                params["continue_send"] = False
            return EventDecision.STOP, params

        except Exception as e:
            logger.error(f"分段发送失败: {e}", exc_info=True)
            # 发生异常时放行原始消息，保证消息不丢失
            return EventDecision.SUCCESS, params

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _get_config(self) -> Config | None:
        """获取插件配置实例。

        Returns:
            Config 实例，若无法获取则返回 None
        """
        if not self.plugin or not self.plugin.config:
            logger.warning("无法获取插件配置")
            return None
        return cast(Config, self.plugin.config)

    async def _send_segments(self, message: Message, sentences: list[str], config: Config) -> None:
        """逐句发送已分段的消息。

        Args:
            message: 原始消息对象
            sentences: 已分段的句子列表
            config: 插件配置
        """
        snd = config.sending

        if snd.log_progress:
            logger.info(f"消息已分为 {len(sentences)} 段: message_id={message.message_id}")

        # 逐句发送
        for idx, sentence in enumerate(sentences, 1):
            # 打字延迟（模拟人类输入速度）
            typing_delay = self._calc_typing_delay(
                sentence, snd.typing_speed_cps, snd.min_typing_delay, snd.max_typing_delay
            )
            if typing_delay > 0:
                await asyncio.sleep(typing_delay)

            try:
                # 只在第一段保留原消息的 reply_to；其余段作为补充，不带 reply_to
                reply_to = message.reply_to if idx == 1 else None
                
                success = await send_text(
                    content=sentence,
                    stream_id=message.stream_id,
                    platform=message.platform,
                    reply_to=reply_to,
                )

                if success:
                    if config.general.debug_mode:
                        logger.debug(
                            f"第 {idx}/{len(sentences)} 段发送成功: "
                            f"{sentence[:30]}{'...' if len(sentence) > 30 else ''}"
                        )
                else:
                    logger.warning(f"第 {idx}/{len(sentences)} 段发送失败: {sentence[:30]}")
                    if snd.fail_strategy == "stop":
                        logger.info("根据 fail_strategy=stop，停止后续发送")
                        break

            except Exception as e:
                logger.error(f"发送第 {idx} 段时出错: {e}")
                if snd.fail_strategy == "stop":
                    logger.info("根据 fail_strategy=stop，停止后续发送")
                    break

            # 段间固定延迟
            if snd.delay_between_segments > 0 and idx < len(sentences):
                await asyncio.sleep(snd.delay_between_segments)

    @staticmethod
    def _calc_typing_delay(
        text: str,
        typing_speed_cps: float,
        min_delay: float,
        max_delay: float,
    ) -> float:
        """根据文本长度和打字速度计算打字延迟。

        Args:
            text: 待发送文本
            typing_speed_cps: 打字速度（字符/秒），0 表示禁用
            min_delay: 最小延迟（秒）
            max_delay: 最大延迟（秒）

        Returns:
            建议延迟时间（秒）
        """
        if typing_speed_cps <= 0:
            return 0.0
        raw = len(text) / typing_speed_cps
        return max(min_delay, min(max_delay, raw))