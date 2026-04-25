"""每日寄语 wall template: LLM → remote art (Pinterest / pinscrape) → compose_motto.

Env vars: see module docstrings in ``llm.py`` (LLM), ``images.py`` (Pinterest / pinscrape / fallbacks),
``net.py`` (proxy), ``compose.py`` (fonts / scrim).
"""
from __future__ import annotations

import logging

from renderers.template_base import RenderContext, WallTemplate
from renderers.templates.photo_scrim import infer_fetch_size

from .compose import compose_motto
from .images import fetch_web_motto_image, offline_motto_art
from .llm import call_llm_for_motto

log = logging.getLogger(__name__)


class AiMottoTemplate(WallTemplate):
    display_name = "每日寄语"

    def render(self, ctx: RenderContext) -> Image.Image:
        params = ctx.scene.template_params or {}
        w = ctx.device_profile.get("width", 800)
        h = ctx.device_profile.get("height", 600)

        raw_ov = params.get("text")
        override_text = raw_ov.strip() if isinstance(raw_ov, str) else ""
        if override_text:
            log.info("ai_motto: templateParams.text set; using fixed motto, no LLM/web image")
            motto, image_prompt = override_text, None
        else:
            motto, image_prompt = call_llm_for_motto()

        art = None
        gen_w, gen_h = infer_fetch_size(w, h)
        if image_prompt:
            art = fetch_web_motto_image(image_prompt, gen_w, gen_h, motto)
            if art is None:
                log.info("ai_motto: remote image unavailable; using offline wallpaper")
                art = offline_motto_art(gen_w, gen_h)
        elif not override_text:
            art = offline_motto_art(gen_w, gen_h)

        return compose_motto(motto, art, w, h)
