"""Chinese calendar day string for template footers."""

from __future__ import annotations

from datetime import datetime


def cn_date_str() -> str:
    """Today's date in Chinese, e.g. '四月十九日'."""
    now = datetime.now()
    ms = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二"]
    ds = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九"]
    d = now.day
    if d <= 10:
        day = "十" if d == 10 else ds[d]
    elif d < 20:
        day = "十" + ds[d - 10]
    elif d == 20:
        day = "二十"
    elif d < 30:
        day = "二十" + ds[d - 20]
    elif d == 30:
        day = "三十"
    else:
        day = "三十一"
    return f"{ms[now.month - 1]}月{day}日"
