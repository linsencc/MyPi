"""Open-Meteo forecast for weekend outing card."""

from __future__ import annotations

import base64
import json
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from renderers.templates.ai_motto.net import build_llm_proxy_opener

log = logging.getLogger(__name__)

_TIMEOUT = 12


def _short_date(iso: str) -> str:
    """``2026-04-26`` → ``4/26``（省屏宽）。"""
    try:
        parts = str(iso).strip().split("-", 2)
        if len(parts) == 3:
            return f"{int(parts[1])}/{int(parts[2])}"
    except (ValueError, TypeError):
        pass
    return str(iso)

# WMO → OpenWeather 风格图标名（与 InkyPi 等插件一致，用于 cdn 图片 URL）
def wmo_to_owm_icon_id(weather_code: int) -> str:
    wc = int(weather_code)
    if wc == 0:
        return "01d"
    if wc == 1:
        return "02d"
    if wc == 2:
        return "03d"
    if wc == 3:
        return "09d"
    if wc in (45, 48):
        return "50d"
    if wc in (51, 53, 55):
        return "09d"
    if wc in (56, 57):
        return "13d"
    if wc in (61, 63, 65):
        return "10d"
    if wc in (71, 73, 75):
        return "13d"
    if wc in (80, 81, 82):
        return "09d"
    if wc in (95, 96, 99):
        return "11d"
    return "02d"


def owm_icon_url(icon_id: str, *, size: str = "2x") -> str:
    """OpenWeatherMap CDN（仅图标，与 InkyPi 天气插件同类资源）。"""
    return f"https://openweathermap.org/img/wn/{icon_id}@{size}.png"


def inline_owm_icons_for_rows(rows: list[dict[str, Any]], *, timeout_s: float = 8.0) -> None:
    """把图标下载为 data URI 写入 ``icon_src``，供 Chromium 截图时无需再请求外网（避免裂图）。"""
    if not rows:
        return
    opener = build_llm_proxy_opener()
    cache: dict[str, str] = {}
    for row in rows:
        uid = str(row.get("icon_id") or "")
        url = str(row.get("icon_url") or "").strip()
        if not url:
            row["icon_src"] = ""
            continue
        if uid and uid in cache:
            row["icon_src"] = cache[uid]
            continue
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "MyPiWeekendOuting/1.0"},
                method="GET",
            )
            with opener.open(req, timeout=timeout_s) as resp:
                raw = resp.read()
            if len(raw) < 80:
                raise ValueError("icon response too small")
            b64 = base64.b64encode(raw).decode("ascii")
            src = f"data:image/png;base64,{b64}"
            row["icon_src"] = src
            if uid:
                cache[uid] = src
        except Exception as exc:
            log.debug("weekend_outing: OWM icon inline failed %s: %s", url, exc)
            row["icon_src"] = ""


_WMO_DAY: dict[int, str] = {
    0: "晴",
    1: "多云",
    2: "阴",
    3: "阵雨",
    45: "雾",
    48: "冻雾",
    51: "小毛毛雨",
    53: "毛毛雨",
    55: "大毛毛雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    80: "阵雨",
    81: "小阵雨",
    82: "强阵雨",
    95: "雷雨",
    96: "雷雨伴冰雹",
    99: "强雷雨伴冰雹",
}


@dataclass
class WeatherDigest:
    lines: list[str]
    daily_precip_prob_max: list[int]
    daily_temp_max: list[float]
    daily_temp_min: list[float]
    #: 供 HTML 模板：每日一行结构化 + 图标 URL（与 ``lines`` 同源数据）
    daily_rows: list[dict[str, Any]] | None = None


def fetch_weather_digest(
    lat: float,
    lon: float,
    *,
    forecast_days: int,
    include_hourly_today: bool,
) -> WeatherDigest | None:
    fd = str(max(1, min(7, forecast_days)))
    daily_q = urllib.parse.urlencode(
        {
            "latitude": f"{lat:.4f}",
            "longitude": f"{lon:.4f}",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weathercode",
            "hourly": "temperature_2m,precipitation_probability,weathercode",
            "timezone": "Asia/Shanghai",
            "forecast_days": fd,
        }
    )
    url = f"https://api.open-meteo.com/v1/forecast?{daily_q}"
    opener = build_llm_proxy_opener()
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "MyPiWeekendOuting/1.0"},
            method="GET",
        )
        with opener.open(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        log.warning("weekend_outing: open-meteo failed: %s", exc)
        return None

    try:
        daily = data["daily"]
        times = daily["time"]
        tmax = daily["temperature_2m_max"]
        tmin = daily["temperature_2m_min"]
        pprob = daily["precipitation_probability_max"]
        wcode = daily["weathercode"]
    except (KeyError, TypeError) as exc:
        log.warning("weekend_outing: open-meteo unexpected daily shape: %s", exc)
        return None

    lines: list[str] = ["【天气】"]
    daily_rows: list[dict[str, Any]] = []
    probs: list[int] = []
    tmax_f: list[float] = []
    tmin_f: list[float] = []
    for i, day in enumerate(times):
        if i >= len(tmax) or i >= len(tmin) or i >= len(pprob) or i >= len(wcode):
            break
        try:
            p = int(pprob[i]) if pprob[i] is not None else 0
        except (TypeError, ValueError):
            p = 0
        probs.append(max(0, min(100, p)))
        try:
            tmax_f.append(float(tmax[i]))
            tmin_f.append(float(tmin[i]))
        except (TypeError, ValueError):
            tmax_f.append(0.0)
            tmin_f.append(0.0)
        wc = int(wcode[i]) if wcode[i] is not None else 0
        desc = _WMO_DAY.get(wc, "多变")
        oid = wmo_to_owm_icon_id(wc)
        lines.append(
            f"{_short_date(day)}  {desc}  {tmin[i]}～{tmax[i]}℃  雨{p}%"
        )
        try:
            tmi = float(tmin[i])
            tma = float(tmax[i])
        except (TypeError, ValueError):
            tmi, tma = 0.0, 0.0
        daily_rows.append(
            {
                "date": _short_date(day),
                "desc": desc,
                "tmin": tmi,
                "tmax": tma,
                "rain_pct": p,
                "icon_id": oid,
                "icon_url": owm_icon_url(oid),
            }
        )

    if include_hourly_today:
        ht = data.get("hourly") or {}
        htimes = ht.get("time") or []
        htemp = ht.get("temperature_2m") or []
        hp = ht.get("precipitation_probability") or []
        parts: list[str] = []
        for j in range(0, min(len(htimes), 24), 3):
            if j >= len(htemp) or j >= len(hp):
                break
            slot = str(htimes[j]).replace("T", " ")
            if len(slot) > 16:
                slot = slot[5:16]
            parts.append(f"{slot}约{htemp[j]}℃雨{hp[j]}%")
            if len(parts) >= 5:
                break
        if parts:
            lines.append("今日逐时简况：" + "；".join(parts))

    return WeatherDigest(
        lines=lines,
        daily_precip_prob_max=probs,
        daily_temp_max=tmax_f,
        daily_temp_min=tmin_f,
        daily_rows=daily_rows or None,
    )


def digest_for_jinja(digest: WeatherDigest | None) -> dict[str, Any]:
    """Structured view for HTML/Jinja (深圳 Open-Meteo digest + 图标行)."""
    if not digest:
        return {
            "has_weather": False,
            "daily_lines": [],
            "daily_rows": [],
            "hourly_line": None,
        }
    daily_lines: list[str] = []
    hourly_line: str | None = None
    for ln in digest.lines[1:]:
        if ln.startswith("今日逐时"):
            hourly_line = ln
        else:
            daily_lines.append(ln)
    rows = [dict(r) for r in (digest.daily_rows or [])]
    inline_owm_icons_for_rows(rows)
    return {
        "has_weather": True,
        "daily_lines": daily_lines,
        "daily_rows": rows,
        "hourly_line": hourly_line,
    }


def heuristic_tip(digest: WeatherDigest | None) -> str:
    if not digest or not digest.daily_precip_prob_max:
        return "【提示】留意天气变化，合理安排室内外活动。"
    probs = digest.daily_precip_prob_max
    hi = max(probs) if probs else 0
    tmax = digest.daily_temp_max
    tmin = digest.daily_temp_min
    span = 0.0
    if tmax and tmin:
        span = max(tmax) - min(tmin)
    bits: list[str] = []
    if hi >= 60:
        bits.append("周末降水概率偏高，可优先室内或备雨具。")
    elif hi >= 35:
        bits.append("局部可能有雨，外出建议带伞。")
    if span >= 8:
        bits.append("昼夜温差较大，注意增减衣物。")
    if not bits:
        bits.append("天气整体较平稳，适合按兴趣安排出行。")
    return "【提示】" + "".join(bits)
