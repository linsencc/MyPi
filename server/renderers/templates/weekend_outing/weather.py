"""Open-Meteo forecast for weekend outing card."""

from __future__ import annotations

import base64
import json
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date
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


_WD_CN = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


def _weekday_cn_from_iso(iso_day: str) -> str:
    """``2026-04-26`` → ``周六``（本地日历周几）。"""
    try:
        y, mo, d = (int(x) for x in str(iso_day).strip().split("-", 2)[:3])
        wd = date(y, mo, d).weekday()
        return _WD_CN[wd]
    except (ValueError, TypeError, IndexError):
        return ""


def _bi_class_for_data_weather(dw: str) -> str:
    """Bootstrap Icons 类名，与静态稿 ``weekend-outing-shenzhen-1200x1600.html`` 一致。"""
    return {
        "sunny": "bi bi-sun",
        "cloudy": "bi bi-clouds",
        "showers-low": "bi bi-cloud-rain",
        "showers-mid": "bi bi-cloud-drizzle",
        "rain-moderate": "bi bi-cloud-rain-heavy",
    }.get(str(dw), "bi bi-cloud-rain")


def _data_weather_attr(weather_code: int, rain_pct: int) -> str:
    """与 ``weekend.css`` 中 ``[data-weather]`` 配色一致的气象槽位名。"""
    wc = int(weather_code)
    p = int(rain_pct)
    if wc == 0:
        return "sunny"
    if wc in (1, 2, 45, 48):
        return "cloudy"
    if wc in (3, 80, 81, 82):
        if p < 22:
            return "showers-low"
        if p < 52:
            return "showers-mid"
        return "rain-moderate"
    if wc in (51, 53, 55, 61):
        if p < 28:
            return "showers-low"
        if p < 55:
            return "showers-mid"
        return "rain-moderate"
    if wc in (63, 65, 95, 96, 99):
        return "rain-moderate"
    if wc in (71, 73, 75):
        return "cloudy"
    return "showers-mid"

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
        dw = _data_weather_attr(wc, p)
        daily_rows.append(
            {
                "iso": str(day).strip(),
                "date": _short_date(day),
                "weekday": _weekday_cn_from_iso(str(day)),
                "desc": desc,
                "tmin": tmi,
                "tmax": tma,
                "rain_pct": p,
                "data_weather": dw,
                "bi_class": _bi_class_for_data_weather(dw),
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


def weather_risk_context_for_llm(digest: WeatherDigest | None) -> str:
    """供「建议」LLM 判断是否在文案中提及天气：空串表示禁止讨论一般天气/交通。

    仅在有强对流、极端降水、高温、低温或明显昼夜温差等情况下返回简短说明。
    """
    if not digest:
        return ""
    probs = digest.daily_precip_prob_max or []
    hi = max(probs) if probs else 0
    lines = [ln for ln in (digest.lines or [])[1:] if not str(ln).startswith("今日逐时")]
    stormish = any(
        any(k in str(ln) for k in ("雷雨", "冰雹", "雷暴", "强对流", "强阵雨"))
        for ln in lines
    )
    tmaxs = digest.daily_temp_max or []
    tmins = digest.daily_temp_min or []
    tmax_peak = max(tmaxs) if tmaxs else 0.0
    tmin_floor = min(tmins) if tmins else 99.0
    span = (max(tmaxs) - min(tmins)) if tmaxs and tmins else 0.0

    if stormish or hi >= 88:
        return (
            "存在雷雨、冰雹或降水概率极高等情况；仅在必要时用一两句提醒安全、改室内或关注预警，"
            "勿复述上方天气栏已展示的温度与晴雨描述。"
        )
    if hi >= 72:
        return (
            f"多日降水概率偏高（最高约 {hi}%），可能影响露天或长途户外类活动；若列表含相关场次，可简要说明影响或替代，"
            "勿写雨具、穿衣、地铁串连等日常出行提示。"
        )
    if hi >= 58:
        return (
            f"部分日期降水概率较高（最高约 {hi}%）；仅当所列活动明显依赖户外时，可用一句点到为止，"
            "否则不要讨论天气。"
        )
    if tmax_peak >= 35.0:
        return "预报期间可能出现高温天气；仅当活动含长时间户外时，用一句提醒防暑补水，勿展开一般穿衣建议。"
    if tmin_floor <= 2.0:
        return "预报期间可能出现低温；仅当活动含清晨或夜间户外时，用一句提醒保暖。"
    if span >= 12.0:
        return "昼夜温差较大；仅当活动跨晨昏且偏户外时，可用半句提醒增减衣物，勿写常规穿衣唠叨。"
    return ""


def weather_risk_one_liner(digest: WeatherDigest | None) -> str:
    """无 LLM 时可选缀在建议后的极短风险提示（多数情况为空）。"""
    if not digest or not digest.daily_precip_prob_max:
        return ""
    probs = digest.daily_precip_prob_max or []
    hi = max(probs) if probs else 0
    lines = [ln for ln in (digest.lines or [])[1:] if not str(ln).startswith("今日逐时")]
    if any(any(k in str(ln) for k in ("雷雨", "冰雹", "雷暴", "强对流")) for ln in lines):
        return "请关注强对流与出行安全。"
    if hi >= 80:
        return "连日多雨，露天行程易受影响。"
    if hi >= 65:
        return "部分日期多雨，户外场次留意改期。"
    tmaxs = digest.daily_temp_max or []
    if tmaxs and max(tmaxs) >= 35.0:
        return "有高温天气，户外注意防暑。"
    return ""
