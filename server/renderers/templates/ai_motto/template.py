"""AI-generated daily message template with a Pinterest-sourced illustration.

Implementation is split across ``prompts``, ``net``, ``llm``, ``images``, and ``compose`` in this package.

Targets **full-color RGB** for color e-ink. Downloaded photos are rejected if they look **black &
white**; if no color image is found after retries, the layout falls back to **text only** (no art).

Each render:
  1. Calls LLM to generate a Chinese motto + English image prompt (landscape / scenery, any style)
  2. Fetches a full-color landscape image from **Pinterest only** by default (optional stock fallbacks; see ``images``)
  3. Composes a full-bleed image with text overlay (portrait-friendly, image is cropped to the frame)

Environment variables:
  MYPI_LLM_API_KEY             – OpenAI-compatible API key (e.g. OpenRouter)
  MYPI_LLM_BASE_URL            – API base URL (default: https://openrouter.ai/api/v1)
  MYPI_LLM_MODEL               – Model id (default: deepseek/deepseek-chat on OpenRouter)
  MYPI_LLM_TIMEOUT             – LLM timeout seconds (default: 20)
  MYPI_LLM_PROXY               – HTTP(S) proxy for LLM calls
  MYPI_PINTEREST_ACCESS_TOKEN  – Pinterest API OAuth access token (or PINTEREST_ACCESS_TOKEN)
  MYPI_PINTEREST_COUNTRY       – ISO 3166-1 alpha-2 for partner search (default: US)
  MYPI_PINTEREST_BOARD_ID      – Optional numeric board id (same Pinterest account as token)
  MYPI_MOTTO_FETCH_MAX_SIDE    – Max long edge when downloading (see photo_scrim.infer_fetch_size)
  MYPI_MOTTO_COLOR_BOOST       – PIL color boost after download (see photo_scrim.to_full_color_rgb)
  MYPI_MOTTO_BEAUTIFY          – if 0: skip mild contrast/sat on downloaded art (default: 1 / on)
  MYPI_MOTTO_SCRIM_MAX         – bottom dark scrim max opacity (see photo_scrim.overlay_bottom_scrim)
  MYPI_MOTTO_FONT              – Optional path to .ttf/.otf/.ttc for the quote
  MYPI_MOTTO_FONT_BOLD         – Optional path to a bolder face for the quote
  MYPI_MOTTO_IMAGE_NO_PROXY      – if 1/true: Pinterest/image HTTP without proxy (LLM may still use proxy)
  MYPI_MOTTO_STOCK_FALLBACK      – if 1/true: when Pinterest fails, try LoremFlickr/Picsum (default: off = Pinterest-only)
  MYPI_MOTTO_OFFLINE_IMAGE       – Optional path to a JPEG/PNG when remote image fetch fails
"""
from __future__ import annotations

import logging

from PIL import Image

from renderers.template_base import RenderContext, WallTemplate
from .compose import compose_motto
from .images import (
    fetch_web_motto_image,
    offline_motto_art,
)
from .llm import call_llm_for_motto
from renderers.templates.photo_scrim import infer_fetch_size

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
