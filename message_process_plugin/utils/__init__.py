"""
消息分段工具函数

提供文本智能分段所需的保护/恢复机制与核心分割逻辑。
迁移自旧框架 src/chat/utils/utils.py 中的 split_into_sentences_w_remove_punctuation 逻辑。
"""

import random
import re

from .split_utils import _replace_all, protect_kaomoji, protect_pairs, protect_quoted_content, protect_special_blocks, protect_urls

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
    preserve_punctuation: bool = True,
    enable_kaomoji: bool = True,
    enable_quote: bool = True,
    enable_code_block: bool = True,
    enable_url: bool = True,
    enable_pair: bool = True,
    separators: list[str] | None = None,
    strong_separators: list[str] | None = None,
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
        preserve_punctuation: 是否在句末保留标点符号（False 时去除弱标点）
        enable_url: 是否保护 URL
        enable_pair: 是否保护成对括号内容
        separators: 分割点字符列表，None 时使用内置默认值
        strong_separators: 强语义分隔符集合，这些字符在分段后保留在句尾，None 时使用内置默认值

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

    # ── 分隔符集合（可由调用方通过 separators 参数覆盖）
    _sep_set: set[str] = set(separators) if separators is not None else {
        "，", ",", " ", "。", ";", "∽", "≈", "~", "～", "…", "！", "!", "？", "?"
    }
    _strong_sep_set: set[str] = set(strong_separators) if strong_separators is not None else {
        "∽", "≈", "~", "～", "…", "！", "!", "？", "?", "♪"
    }

    # ── 按分隔符切分成 (内容, 分隔符) 元组
    segments: list[tuple[str, str]] = []
    current_segment = ""
    i = 0

    while i < len(text):
        char = text[i]
        if char in _sep_set:
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
                split_strength = 0.6
            else:
                split_strength = 0.7
        else:
            split_strength = float(base_split_strength)
        merge_probability = 1.0 - split_strength
    else:
        merge_probability = 0.0

    # ── 概率合并（与旧框架对齐）
    # 按标点类型调整合并概率：强标点难合并，弱标点易合并；
    # 使用独立输出列表 + idx+=2 防止链式合并（旧框架逻辑）
    merged_segments: list[tuple[str, str]] = []
    idx = 0
    while idx < len(segments):
        current_content, current_sep = segments[idx]

        # 按标点类型调整本次合并概率（动态使用 _strong_sep_set，不再硬编码）
        current_merge_prob = merge_probability
        if current_sep in {"。", "；", ";"}:
            current_merge_prob *= 0.1   # 句终标点：极难合并
        elif current_sep in _strong_sep_set:
            current_merge_prob *= 0.3   # 强语义符号（感叹、问号、波浪、♪ 等）：较难合并
        else:
            current_merge_prob *= 1.2   # 弱标点（逗号、空格等）：更容易合并

        if (
            idx + 1 < len(segments)
            and random.random() < current_merge_prob
            and current_content
        ):
            next_content, next_sep = segments[idx + 1]
            if next_content:
                merged_segments.append((current_content + current_sep + next_content, next_sep))
            else:
                merged_segments.append((current_content, next_sep))
            idx += 2  # 跳过已合并的下一段，避免链式合并
        else:
            merged_segments.append((current_content, current_sep))
            idx += 1

    # ── 提取初步句子
    # 强语义符号保留在句尾；弱功能性标点在分割点去掉，因为分段本身已起到停顿作用。
    # 最后一段无论什么符号都保留（与旧框架一致）。
    final_sentences: list[str] = []
    for i, (content, sep) in enumerate(merged_segments):
        if not content:
            continue
        if i == len(merged_segments) - 1 or sep in _strong_sep_set:
            sentence = (content + sep).strip()
        else:
            sentence = content.strip()
        if sentence:
            final_sentences.append(sentence)

    if not final_sentences:
        return []

    # ── 超过 max_segments 时，循环合并最短相邻段
    # 以强标点结尾的段增加合并阻力，避免破坏语义边界；
    # 合并时若前句末尾无标点，自动补 ，（与旧框架逻辑一致）。
    _strong_ending = tuple(_strong_sep_set) + ("。", "；", ";")
    while len(final_sentences) > max_segments:
        min_cost = float("inf")
        min_idx = 0
        for j in range(len(final_sentences) - 1):
            resistance = 5.0 if final_sentences[j].endswith(_strong_ending) else 1.0
            cost = (len(final_sentences[j]) + len(final_sentences[j + 1])) * resistance
            if cost < min_cost:
                min_cost = cost
                min_idx = j
        prev = final_sentences[min_idx]
        nxt = final_sentences[min_idx + 1]
        # 前句末尾无标点时补逗号，保持可读性
        if prev and prev[-1] not in set(_strong_ending) | {"，", ",", "。", "；", ";", " "}:
            final_sentences[min_idx] = prev + "，" + nxt
        else:
            final_sentences[min_idx] = prev + nxt
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

    # ── 统一清理：去除每个独立消息末尾的弱标点符号（保留问号、感叹号、波浪号等强烈语义符号）
    result: list[str] = []
    for s in cleaned_sentences:
        if not preserve_punctuation:
            s = s.rstrip(" ，,。;；")
        if s.strip():
            result.append(s.strip())

    return result

