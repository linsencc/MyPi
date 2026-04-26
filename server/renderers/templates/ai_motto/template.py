"""每日寄语 wall template: LLM → Pinscrape art (or offline) → compose_motto.

Env vars: see ``llm.py`` (LLM), ``images.py`` (Pinscrape / offline), ``net.py`` (proxy), ``compose.py`` (fonts / scrim).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, ClassVar

from PIL import Image

from renderers.template_base import RenderContext, WallTemplate
from renderers.templates.photo_scrim import infer_fetch_size
from renderers.templates.ui_params import _coerce_bool_value, load_param_schema_json

from .compose import compose_motto
from .images import fetch_web_motto_image, offline_motto_art
from .llm import call_llm_for_motto, call_llm_for_wallpaper_image_prompt

log = logging.getLogger(__name__)


class AiMottoTemplate(WallTemplate):
    display_name = "每日寄语"
    param_schema: ClassVar[list[dict[str, Any]]] = load_param_schema_json(
        Path(__file__).resolve().parent / "param_schema.json"
    )

    def render(self, ctx: RenderContext) -> Image.Image:
        params = ctx.scene.template_params or {}
        w = ctx.device_profile.get("width", 800)
        h = ctx.device_profile.get("height", 600)

        raw_ov = params.get("text")
        override_text = raw_ov.strip() if isinstance(raw_ov, str) else ""
        with_image = _coerce_bool_value(params.get("with_image"), True)

        if override_text:
            log.info("ai_motto: templateParams.text set; using fixed motto (motto LLM skipped)")
            motto = override_text
        else:
            motto = call_llm_for_motto()
        # 开底图时与「全自动生成」一致：壁纸英文 prompt 仍由独立 LLM（或无 key 时 None）→ 画板 / pinscrape；仅与寄语正文生成解耦
        image_prompt = call_llm_for_wallpaper_image_prompt() if with_image else None

        art = None
        gen_w, gen_h = infer_fetch_size(w, h)
        if with_image:
            if image_prompt:
                art = fetch_web_motto_image(image_prompt, gen_w, gen_h, motto)
                if art is None:
                    log.info("ai_motto: remote image unavailable; using offline wallpaper")
                    art = offline_motto_art(gen_w, gen_h)
            else:
                art = offline_motto_art(gen_w, gen_h)
        else:
            log.info("ai_motto: with_image=false; text-only card, no art")

        return compose_motto(motto, art, w, h)
