# ---------------------------------------------------------------------------
# 内容保护 / 恢复工具
# ---------------------------------------------------------------------------


import re


def protect_kaomoji(text: str) -> tuple[str, dict[str, str]]:
    """识别并保护颜文字不被分割。

    Args:
        text: 待处理文本

    Returns:
        tuple[str, dict[str, str]]: (保护后的文本, 占位符→原文映射)
    """
    placeholder_map: dict[str, str] = {}
    # 匹配常见颜文字模式：括号包裹的特殊字符序列
    kaomoji_pattern = re.compile(
        r"[（(][^\n（(）)]{1,30}[）)]"          # 括号包裹的短序列
        r"|[╯╰┻┳ヽ/\\ノ]+[°д°≧≦＾﹏☆♡；ｗw]+"  # 特殊符号组合
        r"|[qQ][^\s_]{0,5}[qQ]"                # qwq / QAQ 类
        r"|[^a-zA-Z0-9\u4e00-\u9fff\s]{3,}"    # 连续3个以上非常规字符
    )

    idx = 0

    def _replace(m: re.Match) -> str:
        nonlocal idx
        key = f"__KAOMOJI_{idx}__"
        placeholder_map[key] = m.group(0)
        idx += 1
        return key

    return kaomoji_pattern.sub(_replace, text), placeholder_map


def recover_kaomoji(sentences: list[str], mapping: dict[str, str]) -> list[str]:
    """恢复被保护的颜文字。

    Args:
        sentences: 句子列表
        mapping: 占位符→原文映射

    Returns:
        恢复后的句子列表
    """
    return [_replace_all(s, mapping) for s in sentences]


def protect_quoted_content(text: str) -> tuple[str, dict[str, str]]:
    """识别并保护引号包裹的内容不被分割。

    Args:
        text: 待处理文本

    Returns:
        tuple[str, dict[str, str]]: (保护后的文本, 占位符→原文映射)
    """
    placeholder_map: dict[str, str] = {}
    quote_pattern = re.compile(r'(".*?")|(\'.*?\')|(\u201c.*?\u201d)|(\u2018.*?\u2019)')
    match_list = list(quote_pattern.finditer(text))
    # 从后往前替换，避免索引偏移
    for i, m in enumerate(reversed(match_list)):
        key = f"__QUOTE_{i}__"
        start, end = m.start(), m.end()
        placeholder_map[key] = text[start:end]
        text = text[:start] + key + text[end:]
    return text, placeholder_map


def recover_quoted_content(sentences: list[str], mapping: dict[str, str]) -> list[str]:
    """恢复被保护的引号内容。

    Args:
        sentences: 句子列表
        mapping: 占位符→原文映射

    Returns:
        恢复后的句子列表
    """
    return [_replace_all(s, mapping) for s in sentences]


def protect_special_blocks(text: str) -> tuple[str, dict[str, str]]:
    """识别并保护代码块和数学公式不被分割。

    Args:
        text: 待处理文本

    Returns:
        tuple[str, dict[str, str]]: (保护后的文本, 占位符→原文映射)
    """
    placeholder_map: dict[str, str] = {}
    idx = 0
    patterns = {
        "code": r"```.*?```",
        "math": r"\$\$.*?\$\$",
    }
    for _, pattern in patterns.items():
        for m in re.finditer(pattern, text, re.S):
            key = f"__BLOCK_{idx}__"
            placeholder_map[key] = m.group(0)
            text = text.replace(m.group(0), key, 1)
            idx += 1
    return text, placeholder_map


def recover_special_blocks(sentences: list[str], mapping: dict[str, str]) -> list[str]:
    """恢复被保护的代码块和数学公式。

    Args:
        sentences: 句子列表
        mapping: 占位符→原文映射

    Returns:
        恢复后的句子列表
    """
    return [_replace_all(s, mapping) for s in sentences]


def protect_urls(text: str) -> tuple[str, dict[str, str]]:
    """识别并保护 URL 不被分割。

    Args:
        text: 待处理文本

    Returns:
        tuple[str, dict[str, str]]: (保护后的文本, 占位符→原文映射)
    """
    placeholder_map: dict[str, str] = {}
    url_pattern = r'https?://[^\s，。！？"）》]+'
    urls = re.findall(url_pattern, text)
    for i, url in enumerate(urls):
        key = f"__URL_{i}__"
        placeholder_map[key] = url
        text = text.replace(url, key, 1)
    return text, placeholder_map


def protect_pairs(text: str) -> tuple[str, dict[str, str]]:
    """识别并保护成对括号内容不被分割。

    Args:
        text: 待处理文本

    Returns:
        tuple[str, dict[str, str]]: (保护后的文本, 占位符→原文映射)
    """
    placeholder_map: dict[str, str] = {}
    pair_pattern = r"([（\(《「].*?[）\)》」])"
    pairs = re.findall(pair_pattern, text)
    for i, pair in enumerate(pairs):
        key = f"__PAIR_{i}__"
        placeholder_map[key] = pair
        text = text.replace(pair, key, 1)
    return text, placeholder_map


def _replace_all(text: str, mapping: dict[str, str]) -> str:
    """批量替换文本中的所有占位符。

    Args:
        text: 待处理文本
        mapping: 占位符→原文映射

    Returns:
        替换后的文本
    """
    for key, value in mapping.items():
        text = text.replace(key, value)
    return text
