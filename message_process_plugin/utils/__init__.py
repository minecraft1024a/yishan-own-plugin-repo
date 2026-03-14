"""
消息分段工具函数

提供文本智能分段所需的保护/恢复机制与核心分割逻辑。
迁移自旧框架 src/chat/utils/utils.py 中的 split_into_sentences_w_remove_punctuation 逻辑。
"""

import random
import re

from split_utils import _replace_all, protect_kaomoji, protect_pairs, protect_quoted_content, protect_special_blocks, protect_urls

# ---------------------------------------------------------------------------
# 核心分割逻辑（迁移自旧框架 split_into_sentences_w_remove_punctuation）
# ---------------------------------------------------------------------------


def _is_english_letter(char: str) -> bool:
    """判断字符是否为英文字母（ASCII 范围）。

    Args:
        char: 单个字符

    Returns:
        是否为英文字母
    """
    return char.isalpha() and ord(char) < 128


def split_into_sentences(
    text: str,
    base_split_strength: float = -1.0,
    enable_merge: bool = True,
    max_segments: int = 8,
    enable_kaomoji: bool = True,
    enable_quote: bool = True,
    enable_code_block: bool = True,
    enable_url: bool = True,
    enable_pair: bool = True,
) -> list[str]:
    """将文本分割成句子，并根据概率合并相邻短句。

    分割流程：
    1. 多层内容保护（颜文字、引号、代码块、URL、括号）
    2. 预处理换行符
    3. 在标点处分割（英文字母两侧不分割）
    4. 概率合并相邻弱标点段落（模拟人类打字节奏）
    5. 超过 max_segments 时智能合并最短相邻段
    6. 恢复所有被保护的内容

    Args:
        text: 要分割的文本
        base_split_strength: 分割强度 (0.0~1.0)，-1 表示按文本长度自动调整
        enable_merge: 是否启用概率合并
        max_segments: 最大分段数量
        enable_kaomoji: 是否保护颜文字
        enable_quote: 是否保护引号内容
        enable_code_block: 是否保护代码块和公式
        enable_url: 是否保护 URL
        enable_pair: 是否保护成对括号内容

    Returns:
        分割并合并后的句子列表
    """
    if not text or not text.strip():
        return []

    # ── 第一层：保护颜文字
    kaomoji_map: dict[str, str] = {}
    if enable_kaomoji:
        text, kaomoji_map = protect_kaomoji(text)

    # ── 第二层：保护引号内容
    quote_map: dict[str, str] = {}
    if enable_quote:
        text, quote_map = protect_quoted_content(text)

    # ── 第三层：保护代码块 / 公式
    block_map: dict[str, str] = {}
    if enable_code_block:
        text, block_map = protect_special_blocks(text)

    # ── 第四层：保护 URL
    url_map: dict[str, str] = {}
    if enable_url:
        text, url_map = protect_urls(text)

    # ── 第五层：保护成对括号
    pair_map: dict[str, str] = {}
    if enable_pair:
        text, pair_map = protect_pairs(text)

    # ── 预处理换行符
    text = re.sub(r"\n\s*\n+", "\n", text)
    text = re.sub(r"\n\s*([，,。;\s])", r"\1", text)
    text = re.sub(r"([，,。;\s])\s*\n", r"\1", text)
    text = re.sub(r"([\u4e00-\u9fff])\n([\u4e00-\u9fff])", r"\1。\2", text)

    len_text = len(text)
    if len_text < 3:
        sentence = text.strip()
        return [sentence] if sentence else []

    # ── 分隔符集合（与旧框架保持一致）
    separators = {"，", ",", " ", "。", ";", "∽", "≈", "~", "～", "…", "！", "!", "？", "?"}

    # ── 按分隔符切分成 (内容, 分隔符) 元组
    segments: list[tuple[str, str]] = []
    current_segment = ""
    i = 0

    while i < len(text):
        char = text[i]
        if char in separators:
            # 英文字母两侧不在空格/逗号处分割（保持英文句子完整）
            if char in {" ", ","}:
                left = text[i - 1] if i > 0 else ""
                right = text[i + 1] if i + 1 < len(text) else ""
                if _is_english_letter(left) and _is_english_letter(right):
                    current_segment += char
                    i += 1
                    continue
            segments.append((current_segment, char))
            current_segment = ""
        else:
            current_segment += char
        i += 1

    if current_segment:
        segments.append((current_segment, ""))

    # 过滤全空的段
    segments = [(c, s) for c, s in segments if c.strip() or not c]
    if not segments:
        return []

    # ── 计算合并概率
    if enable_merge:
        if base_split_strength < 0:
            # 按文本长度自动调整（与旧框架一致）
            if len_text < 12:
                split_strength = 0.2
            elif len_text < 32:
                split_strength = 0.4
            else:
                split_strength = 0.7
        else:
            split_strength = float(base_split_strength)
        merge_probability = 1.0 - split_strength
    else:
        merge_probability = 0.0

    # ── 概率合并，仅在弱标点（逗号、顿号、空格）处合并
    weak_separators = {",", "，", " "}
    idx = 0
    while idx < len(segments):
        content, sep = segments[idx]
        if (
            idx + 1 < len(segments)
            and sep in weak_separators
            and random.random() < merge_probability
        ):
            next_content, next_sep = segments[idx + 1]
            segments[idx + 1] = (content + sep + next_content, next_sep)
            segments.pop(idx)
        else:
            idx += 1

    # ── 提取最终句子（弱分隔符不保留，强分隔符保留在句末）
    # 弱分隔符：逗号、顿号、分号、句号等结构性标点，分割后从句末丢弃
    # 强分隔符：感叹号、问号、省略号、波浪号等有语义或表达意图的标点，保留在句末
    soft_separators = {" ", "∽", "≈", ",", "，", ";", "；", "。"}
    final_sentences: list[str] = []
    for content, sep in segments:
        if sep and sep not in soft_separators:
            sentence = (content + sep).strip()
        else:
            sentence = content.strip()
        if sentence:
            final_sentences.append(sentence)

    if not final_sentences:
        return []

    # ── 超过 max_segments 时，循环合并最短相邻段
    while len(final_sentences) > max_segments:
        min_len = float("inf")
        min_idx = 0
        for j in range(len(final_sentences) - 1):
            combined = len(final_sentences[j]) + len(final_sentences[j + 1])
            if combined < min_len:
                min_len = combined
                min_idx = j
        final_sentences[min_idx] = final_sentences[min_idx] + final_sentences[min_idx + 1]
        final_sentences.pop(min_idx + 1)

    # ── 恢复所有被保护的内容
    def _recover(s: str) -> str:
        for mapping in [pair_map, url_map, block_map, quote_map, kaomoji_map]:
            s = _replace_all(s, mapping)
        return s

    final_sentences = [_recover(s) for s in final_sentences]

    # ── 后处理：合并过短或只包含特殊符号的句子到前一句
    # 这可能发生在颜文字/表情恢复后，导致孤立的短句
    def _is_content_only_special(s: str) -> bool:
        """判断句子是否只包含非中文、非英文字符和空格"""
        for ch in s:
            if ch.isalnum() or '\u4e00' <= ch <= '\u9fff':  # 数字、英文、中文
                return False
        return True

    cleaned_sentences: list[str] = []
    for sentence in final_sentences:
        if len(cleaned_sentences) > 0 and (len(sentence) < 3 or _is_content_only_special(sentence)):
            # 合并到前一句
            cleaned_sentences[-1] = cleaned_sentences[-1] + sentence
        else:
            cleaned_sentences.append(sentence)

    return [s for s in cleaned_sentences if s.strip()]

