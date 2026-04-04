from __future__ import annotations

import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from renderers.plugin_base import RenderContext, RenderResult, WallTemplatePlugin


class DailyMottoPlugin(WallTemplatePlugin):
    template_id = "daily_motto"
    display_name = "每日寄语"

    def render(self, ctx: RenderContext) -> RenderResult:
        text = (ctx.scene.template_params or {}).get("text") or "—"
        w, h = 800, 600
        img = Image.new("RGB", (w, h), color=(245, 245, 240))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 36)
        except OSError:
            font = ImageFont.load_default()
        draw.text((40, h // 2 - 20), str(text)[:200], fill=(30, 30, 30), font=font)
        out = Path(ctx.output_dir) / f"daily_motto_{uuid.uuid4().hex}.png"
        img.save(out, format="PNG")
        return RenderResult(image_path=str(out.resolve()))
