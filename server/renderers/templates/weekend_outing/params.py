"""Parse ``templateParams`` for 周末出行 — 默认深圳坐标；条数等由环境变量控制。"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int, lo: int, hi: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return max(lo, min(hi, int(raw)))
    except ValueError:
        return default


def _env_str(name: str, default: str, *, max_len: int = 24) -> str:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return raw[:max_len]


# 深圳南山附近（Open-Meteo）；可通过 MYPI_OUTING_LAT/LON 覆盖
DEFAULT_LAT = 22.5329
DEFAULT_LON = 113.9329
# 副标题与 HTML「天气」分区标题展示用，与坐标解耦（改坐标时记得同步改标签）
DEFAULT_AREA_LABEL = "深圳"


@dataclass(frozen=True)
class WeekendOutingParams:
    latitude: float
    longitude: float
    forecast_days: int
    show_hourly_today: bool
    max_events: int
    enable_llm_weekend_tip: bool
    manual_events_text: str
    area_label: str

    @classmethod
    def from_template_params(cls, raw: dict | None) -> WeekendOutingParams:
        p = raw or {}

        lat = _env_float("MYPI_OUTING_LAT", DEFAULT_LAT)
        lon = _env_float("MYPI_OUTING_LON", DEFAULT_LON)
        forecast_days = _env_int("MYPI_OUTING_FORECAST_DAYS", 3, 1, 7)
        max_events = _env_int("MYPI_OUTING_MAX_EVENTS", 8, 1, 16)
        area_label = _env_str("MYPI_OUTING_AREA_LABEL", DEFAULT_AREA_LABEL, max_len=24)

        show_hourly = _bool_field(p, "show_hourly_today", False)
        enable_llm_tip = _bool_field(p, "enable_llm_weekend_tip", True)

        manual = _str_field(p, "manual_events_text")
        if len(manual) > 2000:
            manual = manual[:2000]

        return cls(
            latitude=lat,
            longitude=lon,
            forecast_days=forecast_days,
            show_hourly_today=show_hourly,
            max_events=max_events,
            enable_llm_weekend_tip=enable_llm_tip,
            manual_events_text=manual,
            area_label=area_label,
        )


def _str_field(p: dict, key: str) -> str:
    v = p.get(key)
    if v is None:
        return ""
    return str(v).strip()


def _bool_field(p: dict, key: str, default: bool) -> bool:
    v = p.get(key)
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)) and v in (0, 1):
        return bool(int(v))
    if isinstance(v, str):
        x = v.strip().lower()
        if x in ("true", "1", "yes", "on"):
            return True
        if x in ("false", "0", "no", "off", ""):
            return False
    return default
