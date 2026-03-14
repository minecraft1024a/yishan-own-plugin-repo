"""时间工具

提供时间相关的辅助功能。
"""

from datetime import datetime, timedelta
from typing import Optional


def get_current_datetime() -> datetime:
    """获取当前日期时间

    Returns:
        当前日期时间对象
    """
    return datetime.now()


def get_weekday_name(date_str: str, language: str = "zh") -> str:
    """获取星期名称

    Args:
        date_str: 日期字符串 (YYYY-MM-DD)
        language: 语言代码 (zh/en)

    Returns:
        星期名称
    """
    date = parse_date(date_str)
    weekday = date.weekday()

    if language == "zh":
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    else:
        weekdays = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]

    return weekdays[weekday]


def is_weekend(date_str: str) -> bool:
    """判断是否是周末

    Args:
        date_str: 日期字符串 (YYYY-MM-DD)

    Returns:
        是否是周末
    """
    date = parse_date(date_str)
    return date.weekday() in [5, 6]  # 5=Saturday, 6=Sunday


def parse_date(date_str: str) -> datetime:
    """解析日期字符串

    Args:
        date_str: 日期字符串 (YYYY-MM-DD)

    Returns:
        日期时间对象
    """
    return datetime.strptime(date_str, "%Y-%m-%d")


def format_date(date: datetime) -> str:
    """格式化日期

    Args:
        date: 日期时间对象

    Returns:
        格式化的日期字符串 (YYYY-MM-DD)
    """
    return date.strftime("%Y-%m-%d")


def get_today_str() -> str:
    """获取今日日期字符串

    Returns:
        今日日期 (YYYY-MM-DD)
    """
    return format_date(get_current_datetime())


def get_tomorrow_str() -> str:
    """获取明日日期字符串

    Returns:
        明日日期 (YYYY-MM-DD)
    """
    tomorrow = get_current_datetime() + timedelta(days=1)
    return format_date(tomorrow)


def get_current_month_str() -> str:
    """获取当前月份字符串

    Returns:
        当前月份 (YYYY-MM)
    """
    return get_current_datetime().strftime("%Y-%m")


def get_next_month_str() -> str:
    """获取下月月份字符串

    Returns:
        下月月份 (YYYY-MM)
    """
    today = get_current_datetime()
    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1)
    else:
        next_month = today.replace(month=today.month + 1)
    return next_month.strftime("%Y-%m")


def get_current_time_str() -> str:
    """获取当前时间字符串

    Returns:
        当前时间 (HH:MM)
    """
    return get_current_datetime().strftime("%H:%M")


def is_time_in_range(time_str: str, time_range: str) -> bool:
    """判断时间是否在范围内

    Args:
        time_str: 时间字符串 (HH:MM)
        time_range: 时间范围 (HH:MM-HH:MM)

    Returns:
        是否在范围内
    """
    try:
        current = datetime.strptime(time_str, "%H:%M")
        parts = time_range.split("-")
        start = datetime.strptime(parts[0], "%H:%M")
        end = datetime.strptime(parts[1], "%H:%M")

        return start <= current < end
    except Exception:
        return False


def parse_time(time_str: str) -> Optional[datetime]:
    """解析时间字符串

    Args:
        time_str: 时间字符串 (HH:MM)

    Returns:
        时间对象，失败返回 None
    """
    try:
        return datetime.strptime(time_str, "%H:%M")
    except Exception:
        return None
