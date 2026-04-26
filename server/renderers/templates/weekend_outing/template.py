"""周末出行：Open-Meteo 深圳天气 + 大模型检索活动（共用 ``MYPI_LLM_*``）+ Jinja/HTML 上屏。

可选环境变量：

- ``MYPI_WEEKEND_HTML``：设为 ``0`` / ``false`` / ``off`` 时**仅**使用内置 PIL 卡片，不调用 Chromium。
- ``MYPI_WEEKEND_CHROMIUM_TIMEOUT``：HTML 截图超时秒数（默认 ``90``）。
- ``MYPI_CHROMIUM_BIN``：Chromium 可执行文件路径（否则自动在 PATH 中查找）。
- ``MYPI_WEEKEND_EVENTS_MODEL``：活动检索所用模型 id；不设置则与 ``MYPI_LLM_MODEL`` 相同。
- 坐标与预报天数：``MYPI_OUTING_LAT`` / ``MYPI_OUTING_LON`` / ``MYPI_OUTING_FORECAST_DAYS`` / ``MYPI_OUTING_MAX_EVENTS``。
- 展示用地名（副标题、HTML「天气」标题）：``MYPI_OUTING_AREA_LABEL``（默认 ``深圳``），与经纬度独立，改坐标时请同步设置。

**调度建议**：在 Web「场景管理」里用 ``cron_weekly`` 配置周五傍晚、周六上午等刷新。

HTML 路径需在设备上安装 ``chromium`` 或 ``chromium-headless-shell``（见 ``server/README.md``）。
"""

from __future__ import annotations

import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from renderers.template_base import RenderContext, WallTemplate
from renderers.templates.ui_params import load_param_schema_json

from . import card, events_grounding, llm_tip, weather
from .params import WeekendOutingParams

log = logging.getLogger(__name__)


def _weekend_html_enabled() -> bool:
    v = os.environ.get("MYPI_WEEKEND_HTML", "").strip().lower()
    if v in ("0", "false", "off", "no"):
        return False
    return True


def _chromium_timeout_s() -> float:
    raw = os.environ.get("MYPI_WEEKEND_CHROMIUM_TIMEOUT", "90").strip()
    try:
        return max(15.0, float(raw))
    except ValueError:
        return 90.0


class WeekendOutingTemplate(WallTemplate):
    display_name = "周末出行"
    param_schema: ClassVar[list[dict[str, Any]]] = load_param_schema_json(
        Path(__file__).resolve().parent / "param_schema.json"
    )

    def render(self, ctx: RenderContext) -> Any:
        params = WeekendOutingParams.from_template_params(ctx.scene.template_params)
        w = int(ctx.device_profile.get("width", 800))
        h = int(ctx.device_profile.get("height", 600))

        def _load_weather() -> weather.WeatherDigest | None:
            return weather.fetch_weather_digest(
                params.latitude,
                params.longitude,
                forecast_days=params.forecast_days,
                include_hourly_today=params.show_hourly_today,
            )

        def _load_events() -> list[str]:
            return events_grounding.fetch_shenzhen_event_lines(max_lines=params.max_events)

        with ThreadPoolExecutor(max_workers=2) as ex:
            fut_w = ex.submit(_load_weather)
            fut_e = ex.submit(_load_events)
            digest = fut_w.result()
            llm_lines = fut_e.result()

        event_lines: list[str] = [t.strip() for t in llm_lines if t.strip()]
        source_labels: list[str] = []
        if event_lines:
            source_labels.append("大模型检索")

        manual = params.manual_events_text.strip()
        if manual:
            parts = [p.strip() for p in re.split(r"[;\n；]+", manual) if p.strip()]
            for r in (parts if parts else [manual]):
                event_lines.append(r)
            source_labels.append("手动")

        event_lines = event_lines[: params.max_events]

        rule = weather.heuristic_tip(digest)
        weather_stub = "；".join(digest.lines[1:4]) if digest and len(digest.lines) > 1 else ""
        act_stub = " / ".join(event_lines[:4]) if event_lines else "无"
        tip: str | None = None
        if params.enable_llm_weekend_tip:
            tip = llm_tip.weekend_tip_one_liner(weather_stub, act_stub)

        rule_display = (
            rule.replace("【提示】", "", 1).strip() if rule.startswith("【提示】") else rule
        )

        if _weekend_html_enabled():
            try:
                from renderers.templates.cn_date import cn_date_str

                from . import html_chromium, jinja_env

                if not os.environ.get("MYPI_LLM_API_KEY", "").strip():
                    empty_events = (
                        "未配置大模型密钥（MYPI_LLM_API_KEY）。请配置与「每日寄语」相同的 OpenRouter 等密钥，"
                        "或在「我想去的活动」里手动填写。"
                    )
                elif not event_lines:
                    empty_events = (
                        "暂无检索结果。可稍后重试本场景，或在「我想去的活动」里手动填写（分号分隔）。"
                    )
                else:
                    empty_events = ""

                tz_name = os.environ.get("MYPI_TZ", "Asia/Shanghai").strip() or "Asia/Shanghai"
                try:
                    z = ZoneInfo(tz_name)
                except ZoneInfoNotFoundError:
                    z = ZoneInfo("Asia/Shanghai")
                last_refresh = datetime.now(z).strftime("%Y-%m-%d %H:%M")

                src = "、".join(dict.fromkeys(source_labels)) if source_labels else "无"
                footer_line = (
                    f"{cn_date_str()}　·　活动：{src}　·　更新 {last_refresh}　·　仅供参考　·　天气 Open-Meteo"
                )

                subtitle = f"{params.area_label} · 出行简报"
                html = jinja_env.render_weekend_layout_html(
                    {
                        "width": w,
                        "height": h,
                        "title": "周末出行",
                        "subtitle": subtitle,
                        "area_label": params.area_label,
                        "weather": weather.digest_for_jinja(digest),
                        "event_lines": event_lines,
                        "empty_events_text": empty_events,
                        "rule": rule_display,
                        "llm_tip": tip or "",
                        "footer_line": footer_line,
                    }
                )
                img = html_chromium.render_html_to_image(
                    html, (w, h), timeout_s=_chromium_timeout_s()
                )
                log.info(
                    "weekend_outing: HTML render ok events=%s sources=%s",
                    len(event_lines),
                    source_labels,
                )
                return img
            except Exception as exc:
                log.warning("weekend_outing: HTML render failed, fallback PIL: %s", exc)

        title_chars = max(22, min(52, w // 16))
        log.info(
            "weekend_outing: PIL render events=%s sources=%s",
            len(event_lines),
            source_labels,
        )
        return card.render_weekend_card(
            width=w,
            height=h,
            digest=digest,
            event_lines=event_lines,
            source_labels=source_labels,
            rule=rule,
            llm_tip=tip,
            title_chars_per_line=title_chars,
            area_label=params.area_label,
        )
