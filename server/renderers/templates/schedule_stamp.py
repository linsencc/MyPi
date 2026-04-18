"""Renders current local time as 月日时分秒 — for visually verifying scheduler / show-now."""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw

from renderers.template_base import RenderContext, WallTemplate
from renderers.templates.daily_motto import _load_cjk_font


def _resolve_tz() -> ZoneInfo:
    name = os.environ.get("MYPI_TZ", "Asia/Shanghai")
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("Asia/Shanghai")


def _format_stamp(now: datetime) -> str:
    # 月日时分秒（无年），与调度对照用
    return now.strftime("%m月%d日 %H:%M:%S")


class ScheduleStampTemplate(WallTemplate):
    display_name = "调度时间戳"

    def render(self, ctx: RenderContext) -> Image.Image:
        tz = _resolve_tz()
        now = datetime.now(tz)
        text = _format_stamp(now)
        w = ctx.device_profile.get("width", 800)
        h = ctx.device_profile.get("height", 600)
        img = Image.new("RGB", (w, h), color=(240, 248, 255))
        draw = ImageDraw.Draw(img)
        scale = min(w, h) / 600
        size_px = max(36, int(56 * scale))
        font = _load_cjk_font(size_px)
        fill = (20, 40, 80)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = max(24, (w - tw) // 2)
        y = max(40, (h - th) // 2)
        draw.text((x, y), text, fill=fill, font=font)
        hint = "schedule_stamp · MYPI_TZ"
        small_size = max(14, int(18 * scale))
        small = _load_cjk_font(small_size)
        hb = draw.textbbox((0, 0), hint, font=small)
        margin = max(24, int(w * 0.04))
        draw.text((margin, h - 48 - (hb[3] - hb[1])), hint, fill=(100, 120, 140), font=small)
        return img
