"""Parse LLM / manual event lines for HTML layout; stable sort by coarse time hints."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

_SPLIT = re.compile(r"\s*[|｜]\s*")
_DAY_HINT = re.compile(r"周[一二三四五六日天]|今天|明天|后天|本周|下周|\d{1,2}月")
_ENUM_PREFIX = re.compile(r"^\s*\d+[\.\)、]\s*")

# 中文「周一」= Python weekday 0 …「周日」= 6
_CN_TO_PY_WD = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}


def _parse_line_parts(raw: str) -> tuple[str, str, str, str]:
    """Split one line into day / category / title / addr（可选第四段：地点）。"""
    t = _ENUM_PREFIX.sub("", (raw or "").strip())
    if not t:
        return "", "", "", ""
    parts = _SPLIT.split(t, maxsplit=3)
    day, cat, title, addr = "", "", "", ""
    if len(parts) >= 4:
        day, cat, title, addr = (
            parts[0].strip(),
            parts[1].strip(),
            parts[2].strip(),
            parts[3].strip(),
        )
    elif len(parts) == 3:
        day, cat, title = parts[0].strip(), parts[1].strip(), parts[2].strip()
    elif len(parts) == 2:
        a, b = parts[0].strip(), parts[1].strip()
        if _DAY_HINT.search(a):
            day, title = a, b
        else:
            cat, title = a, b
    else:
        title = parts[0].strip()
    title = title or t
    return day, cat, title, addr


def _event_kind_class(category: str) -> str:
    """活动卡片装饰类，与 ``weekend.css`` 中 ``.event--*`` 对应。"""
    c = (category or "").strip()
    if "展" in c:
        return "event--exhibition"
    if "讲座" in c or "讲堂" in c or "沙龙" in c:
        return "event--lecture"
    if "市集" in c or "集市" in c or "市场" in c:
        return "event--market"
    if "剧" in c or "戏" in c or "演出" in c:
        return "event--drama"
    if "音乐" in c or "音乐会" in c or "演唱会" in c:
        return "event--music"
    return "event--exhibition"


def rows_for_layout(lines: list[str]) -> list[dict[str, str]]:
    """Split ``日期｜类型｜标题`` 或 ``日期｜类型｜标题｜地址`` into structured rows for Jinja."""
    rows: list[dict[str, str]] = []
    for raw in lines:
        day, cat, title, addr = _parse_line_parts(raw)
        if not (day or cat or title):
            continue
        addr_s = addr.strip()
        day_s = day.strip()
        rows.append(
            {
                "full": raw.strip(),
                "day": day_s,
                "category": cat,
                "title": title,
                "addr": addr_s,
                "when_disp": day_s if day_s else "待定",
                "addr_disp": addr_s if addr_s else "（地址待补充）",
                "event_kind": _event_kind_class(cat),
            }
        )
    return rows


def _day_segment_for_sort(raw: str) -> str:
    return _parse_line_parts(raw)[0]


def _strip_trailing_weekday_cn(s: str) -> str:
    """``4/27 周一`` → ``4/27``，便于匹配 M/D。"""
    return re.sub(r"\s+周[一二三四五六日天]\s*$", "", (s or "").strip()).strip()


# 展示用：只保留「今天起约一个月内」的活动；与模板侧 max 条数配合
DEFAULT_EVENT_RECENCY_DAYS = 31


def _parse_event_calendar_date(day_seg: str, ref: date) -> date | None:
    """从首段日期语解析公历日期；失败则 ``None``（排序时置后）。"""
    s0 = (day_seg or "").strip()
    if not s0:
        return None
    next_week = "下周" in s0
    s = re.sub(r"本周|下周", "", s0).strip() or s0
    bonus = 7 if next_week else 0

    if s in ("今天", "今儿") or s.startswith("今日"):
        return ref + timedelta(days=0 + bonus)
    if s in ("明天", "明日"):
        return ref + timedelta(days=1 + bonus)
    if s in ("后天",):
        return ref + timedelta(days=2 + bonus)

    s_date = _strip_trailing_weekday_cn(s)

    m = re.match(r"^(\d{1,2})月(\d{1,2})日?$", s_date)
    if m:
        mo, d = int(m.group(1)), int(m.group(2))
        y = ref.year
        try:
            dt = date(y, mo, d)
        except ValueError:
            return None
        if dt < ref:
            try:
                dt = date(y + 1, mo, d)
            except ValueError:
                return None
        return dt

    m2 = re.match(r"^(\d{1,2})/(\d{1,2})$", s_date)
    if m2:
        mo, d = int(m2.group(1)), int(m2.group(2))
        y = ref.year
        try:
            dt = date(y, mo, d)
        except ValueError:
            return None
        if dt < ref:
            try:
                dt = date(y + 1, mo, d)
            except ValueError:
                return None
        return dt

    py_wd = _py_weekday_from_cn(s)
    if py_wd is not None:
        tw = ref.weekday()
        days_ahead = (py_wd - tw) % 7
        return ref + timedelta(days=days_ahead + bonus)

    return None


def _ordinal_days_from_ref(day_seg: str, ref: date) -> int | None:
    """无公历解析时的粗序；有日历则用与 ``_parse_event_calendar_date`` 一致的距今天数。"""
    d = _parse_event_calendar_date(day_seg, ref)
    if d is not None:
        return (d - ref).days
    s0 = (day_seg or "").strip()
    if not s0:
        return None
    next_week = "下周" in s0
    bonus = 7 if next_week else 0
    if _DAY_HINT.search(s0):
        return 400 + bonus
    return None


def filter_event_lines_in_recency_window(
    lines: list[str],
    ref: date,
    *,
    window_days: int = DEFAULT_EVENT_RECENCY_DAYS,
) -> list[str]:
    """去掉已过期与超出 ``window_days`` 天的条目；无法解析日期的行保留（如手写待定）。"""
    if not lines:
        return []
    end = ref + timedelta(days=max(1, window_days))
    out: list[str] = []
    for ln in lines:
        seg = _day_segment_for_sort(ln)
        d = _parse_event_calendar_date(seg, ref)
        if d is not None:
            if d < ref or d > end:
                continue
        out.append(ln)
    return out


def _py_weekday_from_cn(s: str) -> int | None:
    """Map 周一…周日 / 六 / 周六 → Python weekday (Mon=0 … Sun=6)."""
    if "周天" in s or "周日" in s:
        return 6
    for ch, py in _CN_TO_PY_WD.items():
        if ch in ("日", "天"):
            continue
        if f"周{ch}" in s:
            return py
    if len(s) == 1:
        return _CN_TO_PY_WD.get(s)
    return None


def sort_event_lines_by_time(
    lines: list[str],
    *,
    now: datetime | None = None,
    tz_name: str = "Asia/Shanghai",
) -> list[str]:
    """Stable sort: coarse time from first ``|`` segment; unknown segments last."""
    if not lines:
        return []
    try:
        from zoneinfo import ZoneInfo

        z = ZoneInfo(tz_name)
    except Exception:
        from zoneinfo import ZoneInfo

        z = ZoneInfo("Asia/Shanghai")
    dt = now or datetime.now(z)
    ref = dt.date()
    keyed: list[tuple[int, date | int, int, str]] = []
    for i, ln in enumerate(lines):
        seg = _day_segment_for_sort(ln)
        d = _parse_event_calendar_date(seg, ref)
        if d is not None:
            keyed.append((0, d, i, ln))
        else:
            ord_ = _ordinal_days_from_ref(seg, ref)
            k = ord_ if ord_ is not None else 10_000
            keyed.append((1, k, i, ln))
    keyed.sort(key=lambda t: (t[0], t[1], t[2]))
    return [t[3] for t in keyed]
