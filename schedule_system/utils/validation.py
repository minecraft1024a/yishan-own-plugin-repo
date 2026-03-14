"""数据验证工具

提供日期、时间等数据的验证功能。
"""

import re
from datetime import datetime
from typing import Optional


def validate_date(date_str: str) -> tuple[bool, Optional[str]]:
    """验证日期格式 (YYYY-MM-DD)

    Args:
        date_str: 日期字符串

    Returns:
        (是否有效, 错误信息)
    """
    if not date_str:
        return False, "日期不能为空"

    pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    if not pattern.match(date_str):
        return False, "日期格式必须为 YYYY-MM-DD"

    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True, None
    except ValueError as e:
        return False, f"日期无效: {e}"


def validate_time_range(time_range: str) -> tuple[bool, Optional[str]]:
    """验证时间范围格式 (HH:MM-HH:MM)

    Args:
        time_range: 时间范围字符串

    Returns:
        (是否有效, 错误信息)
    """
    if not time_range:
        return False, "时间范围不能为空"

    pattern = re.compile(r"^\d{2}:\d{2}-\d{2}:\d{2}$")
    if not pattern.match(time_range):
        return False, "时间范围格式必须为 HH:MM-HH:MM"

    try:
        parts = time_range.split("-")
        start_time = datetime.strptime(parts[0], "%H:%M")
        end_time = datetime.strptime(parts[1], "%H:%M")

        if start_time >= end_time:
            return False, "开始时间必须早于结束时间"

        return True, None
    except ValueError as e:
        return False, f"时间范围无效: {e}"


def validate_month(month_str: str) -> tuple[bool, Optional[str]]:
    """验证月份格式 (YYYY-MM)

    Args:
        month_str: 月份字符串

    Returns:
        (是否有效, 错误信息)
    """
    if not month_str:
        return False, "月份不能为空"

    pattern = re.compile(r"^\d{4}-\d{2}$")
    if not pattern.match(month_str):
        return False, "月份格式必须为 YYYY-MM"

    try:
        datetime.strptime(month_str, "%Y-%m")
        return True, None
    except ValueError as e:
        return False, f"月份无效: {e}"


def validate_priority(priority: int) -> tuple[bool, Optional[str]]:
    """验证优先级 (1-5)

    Args:
        priority: 优先级值

    Returns:
        (是否有效, 错误信息)
    """
    if not isinstance(priority, int):
        return False, "优先级必须是整数"

    if priority < 1 or priority > 5:
        return False, "优先级必须在 1-5 之间"

    return True, None


def validate_activity(activity: str) -> tuple[bool, Optional[str]]:
    """验证活动描述

    Args:
        activity: 活动描述

    Returns:
        (是否有效, 错误信息)
    """
    if not activity:
        return False, "活动描述不能为空"

    if len(activity) > 200:
        return False, "活动描述不能超过 200 个字符"

    return True, None
