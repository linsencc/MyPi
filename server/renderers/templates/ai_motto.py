"""AI-generated daily message template with Civitai illustration.

Each render:
  1. Calls LLM to generate a Chinese motto + English image prompt
  2. Calls Civitai to generate an illustration matching the mood
  3. Composes a two-part layout: image on top, text below

Environment variables:
  MYPI_LLM_API_KEY     – OpenAI-compatible API key
  MYPI_LLM_BASE_URL    – API base URL (default: https://api.openai.com/v1)
  MYPI_LLM_MODEL       – Model name (default: deepseek/deepseek-chat-v3.1)
  MYPI_LLM_TIMEOUT     – LLM timeout seconds (default: 20)
  MYPI_LLM_PROXY       – HTTP(S) proxy for LLM calls
  CIVITAI_TOKEN         – Civitai API token for image generation
  MYPI_CIVITAI_MODEL    – Civitai model URN (default: DreamShaper v8)
  MYPI_CIVITAI_TIMEOUT  – Civitai poll timeout seconds (default: 90)
"""
from __future__ import annotations

import io
import json
import logging
import os
import re as _re
import textwrap
import time
import urllib.error
import urllib.request
from datetime import datetime

from PIL import Image, ImageDraw, ImageFilter

from renderers.template_base import RenderContext, WallTemplate
from renderers.templates.daily_motto import _load_cjk_font, _wrap_lines

log = logging.getLogger(__name__)

# ── LLM config ──────────────────────────────────────────────────────
_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_MODEL = "deepseek/deepseek-chat-v3.1"
_DEFAULT_TIMEOUT = 20

_SYSTEM_PROMPT = textwrap.dedent("""\
    你是一位每天陪伴用户的智慧伙伴。请生成以下两项内容，以纯 JSON 返回：

    {
      "motto": "一句中文寄语",
      "image_prompt": "an English image description"
    }

    严格要求：
    - 只输出上述 JSON，不加任何其他内容、标签或解释
    - motto: 质朴有深度的中文寄语，40 字以内，不说空话套话，不打招呼
    - image_prompt: 一段 50 词以内的英文画面描述，与寄语意境吻合，
      风格偏向自然风光、水彩、或东方美学，适合 Stable Diffusion 生图，
      不要出现文字或人脸
""")

_USER_PROMPT = "请给我今天的一句话和匹配的画面。"

# ── Civitai config ──────────────────────────────────────────────────
_CIVITAI_API = "https://orchestration.civitai.com"
_DEFAULT_CIVITAI_MODEL = "urn:air:sd1:checkpoint:civitai:4384@128713"
_CIVITAI_POLL_INTERVAL = 4
_CIVITAI_TIMEOUT = 90

# ── Fallbacks ───────────────────────────────────────────────────────
_FALLBACK_MESSAGES = (
    "你已经走了很远，别忘了今天也值得好好过。",
    "世间的事，慢慢来，终会有个着落。",
    "心若清净，处处都是道场。",
    "把眼前的事做好，未来自然清晰。",
    "所有走散的，终会以另一种方式归来。",
)


def _get_fallback() -> str:
    i = datetime.now().timetuple().tm_yday % len(_FALLBACK_MESSAGES)
    return _FALLBACK_MESSAGES[i]


def _strip_thinking(text: str) -> str | None:
    text = _re.sub(r"<think>.*?</think>", "", text, flags=_re.DOTALL)
    lines = text.splitlines()
    cjk_lines = [l for l in lines if _re.search(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]", l)]
    result = "\n".join(cjk_lines).strip()
    return result if result else None


def _build_opener(need_proxy: bool = True) -> urllib.request.OpenerDirector:
    if not need_proxy:
        return urllib.request.build_opener()
    proxy = (
        os.environ.get("MYPI_LLM_PROXY", "").strip()
        or os.environ.get("HTTPS_PROXY", "").strip()
        or os.environ.get("https_proxy", "").strip()
    )
    if proxy:
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({"https": proxy, "http": proxy})
        )
    return urllib.request.build_opener()


# ── LLM call ────────────────────────────────────────────────────────

def _call_llm() -> tuple[str, str | None]:
    """Returns (motto, image_prompt). image_prompt may be None."""
    api_key = os.environ.get("MYPI_LLM_API_KEY", "").strip()
    if not api_key:
        return _get_fallback(), None

    base_url = os.environ.get("MYPI_LLM_BASE_URL", _DEFAULT_BASE_URL).rstrip("/")
    model = os.environ.get("MYPI_LLM_MODEL", _DEFAULT_MODEL).strip() or _DEFAULT_MODEL
    timeout = int(os.environ.get("MYPI_LLM_TIMEOUT", str(_DEFAULT_TIMEOUT)))

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _USER_PROMPT},
        ],
        "max_tokens": 400,
        "temperature": 0.9,
    }).encode()

    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/mypi-frame",
            "X-Title": "MyPi Digital Frame",
        },
        method="POST",
    )

    opener = _build_opener()
    try:
        with opener.open(req, timeout=timeout) as resp:
            body = json.loads(resp.read())
        raw = (body["choices"][0]["message"].get("content") or "").strip()
        log.info("ai_motto: LLM raw %d chars", len(raw))

        # Try JSON parse
        cleaned = _re.sub(r"```json\s*|\s*```", "", raw).strip()
        data = json.loads(cleaned)
        motto = data.get("motto", "").strip()
        image_prompt = data.get("image_prompt", "").strip() or None
        if not motto:
            motto = _strip_thinking(raw) or _get_fallback()
        return motto, image_prompt
    except (json.JSONDecodeError, KeyError):
        text = _strip_thinking(raw) if 'raw' in dir() else None
        return text or _get_fallback(), None
    except Exception as exc:
        log.warning("ai_motto: LLM call failed: %s", exc)
        return _get_fallback(), None


# ── Civitai image generation ────────────────────────────────────────

def _generate_civitai_image(prompt: str, width: int, height: int) -> Image.Image | None:
    token = os.environ.get("CIVITAI_TOKEN", "").strip()
    if not token:
        log.debug("ai_motto: CIVITAI_TOKEN not set, skipping image gen")
        return None

    model_urn = os.environ.get("MYPI_CIVITAI_MODEL", _DEFAULT_CIVITAI_MODEL).strip()
    poll_timeout = int(os.environ.get("MYPI_CIVITAI_TIMEOUT", str(_CIVITAI_TIMEOUT)))

    job_payload = json.dumps({
        "$type": "textToImage",
        "model": model_urn,
        "params": {
            "prompt": f"{prompt}, masterpiece, best quality, no text, no watermark",
            "negativePrompt": "(text, watermark, signature, deformed, blurry, lowres:1.4)",
            "scheduler": "EulerA",
            "steps": 20,
            "cfgScale": 7,
            "width": width,
            "height": height,
            "clipSkip": 2,
        },
    }).encode()

    opener = _build_opener()

    # Submit job
    _UA = "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"

    req = urllib.request.Request(
        f"{_CIVITAI_API}/v1/consumer/jobs",
        data=job_payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": _UA,
        },
        method="POST",
    )
    try:
        with opener.open(req, timeout=30) as resp:
            submit = json.loads(resp.read())
        job_token = submit.get("token")
        if not job_token:
            log.warning("ai_motto: Civitai submit returned no token: %s", submit)
            return None
        log.info("ai_motto: Civitai job submitted, token=%s", job_token[:20])
    except Exception as exc:
        log.warning("ai_motto: Civitai submit failed: %s", exc)
        return None

    # Poll for completion
    deadline = time.monotonic() + poll_timeout
    image_url = None
    while time.monotonic() < deadline:
        time.sleep(_CIVITAI_POLL_INTERVAL)
        poll_req = urllib.request.Request(
            f"{_CIVITAI_API}/v1/consumer/jobs?token={job_token}&wait=true",
            headers={"Authorization": f"Bearer {token}", "User-Agent": _UA},
            method="GET",
        )
        try:
            with opener.open(poll_req, timeout=30) as resp:
                status = json.loads(resp.read())
            jobs = status.get("jobs", [])
            if not jobs:
                continue
            job = jobs[0]
            result = job.get("result")
            if isinstance(result, list) and result:
                blob = result[0]
                if isinstance(blob, dict) and blob.get("available"):
                    image_url = blob.get("blobUrl")
                    if image_url:
                        break
            elif isinstance(result, dict):
                image_url = result.get("blobUrl") or result.get("url")
                if image_url:
                    break
            if job.get("scheduled") is False and not result:
                log.warning("ai_motto: Civitai job finished with no result")
                return None
        except Exception as exc:
            log.warning("ai_motto: Civitai poll error: %s", exc)

    if not image_url:
        log.warning("ai_motto: Civitai timed out after %ds", poll_timeout)
        return None

    # Download image
    log.info("ai_motto: Civitai image ready, downloading %s", image_url[:80])
    try:
        dl_req = urllib.request.Request(image_url)
        with opener.open(dl_req, timeout=30) as resp:
            img_data = resp.read()
        return Image.open(io.BytesIO(img_data)).convert("RGB")
    except Exception as exc:
        log.warning("ai_motto: Civitai image download failed: %s", exc)
        return None


# ── Composition ─────────────────────────────────────────────────────

_BG_COLOR = (248, 246, 240)
_TEXT_COLOR = (35, 38, 42)
_SUBTLE_COLOR = (160, 155, 148)
_DIVIDER_COLOR = (220, 216, 210)


def _fit_image(src: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Center-crop & resize to fill target area exactly."""
    src_ratio = src.width / src.height
    tgt_ratio = target_w / target_h
    if src_ratio > tgt_ratio:
        new_h = src.height
        new_w = int(new_h * tgt_ratio)
    else:
        new_w = src.width
        new_h = int(new_w / tgt_ratio)
    left = (src.width - new_w) // 2
    top = (src.height - new_h) // 2
    cropped = src.crop((left, top, left + new_w, top + new_h))
    return cropped.resize((target_w, target_h), Image.LANCZOS)


def _compose(
    motto: str,
    art: Image.Image | None,
    canvas_w: int,
    canvas_h: int,
) -> Image.Image:
    img = Image.new("RGB", (canvas_w, canvas_h), color=_BG_COLOR)
    draw = ImageDraw.Draw(img)
    scale = min(canvas_w, canvas_h) / 600
    margin = max(20, int(canvas_w * 0.04))

    if art:
        # Layout: image takes ~62% height, text takes the rest
        img_area_h = int(canvas_h * 0.62)
        text_area_h = canvas_h - img_area_h

        # Fit and paste the art image
        fitted = _fit_image(art, canvas_w, img_area_h)
        img.paste(fitted, (0, 0))

        # Subtle gradient fade at the bottom edge of image into background
        fade_h = min(40, img_area_h // 8)
        for y in range(fade_h):
            alpha = y / fade_h
            blend = tuple(
                int(px * (1 - alpha) + bg * alpha)
                for px, bg in zip(fitted.getpixel((0, img_area_h - fade_h + y)), _BG_COLOR)
            )
            draw.line([(0, img_area_h - fade_h + y), (canvas_w, img_area_h - fade_h + y)], fill=blend)

        text_y_start = img_area_h
    else:
        # No image: text centered vertically
        text_area_h = canvas_h
        text_y_start = 0

    # ── Draw text ──
    size_px = max(22, int(32 * scale))
    font = _load_cjk_font(size_px)
    max_chars = max(6, int((canvas_w - margin * 2) / (size_px * 1.05)))
    lines = _wrap_lines(motto, max_chars=max_chars, max_lines=4)
    line_h = int(size_px * 1.5)
    block_h = len(lines) * line_h

    # Center text vertically in the text area, slightly above center
    y0 = text_y_start + max(12, (text_area_h - block_h) // 2 - int(10 * scale))

    for k, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = max(margin, (canvas_w - tw) // 2)
        draw.text((x, y0 + k * line_h), line, fill=_TEXT_COLOR, font=font)

    # Attribution
    try:
        small_font = _load_cjk_font(max(11, int(14 * scale)))
        label = "— AI 每日寄语"
        lbbox = draw.textbbox((0, 0), label, font=small_font)
        lw = lbbox[2] - lbbox[0]
        draw.text(
            (canvas_w - lw - margin, canvas_h - int(22 * scale)),
            label,
            fill=_SUBTLE_COLOR,
            font=small_font,
        )
    except Exception:
        pass

    return img


# ── Template class ──────────────────────────────────────────────────

class AiMottoTemplate(WallTemplate):
    display_name = "AI 每日寄语"

    def render(self, ctx: RenderContext) -> Image.Image:
        params = ctx.scene.template_params or {}
        w = ctx.device_profile.get("width", 800)
        h = ctx.device_profile.get("height", 600)

        # Override text from params
        override_text = params.get("text", "").strip()
        if override_text:
            motto, image_prompt = override_text, None
        else:
            motto, image_prompt = _call_llm()

        # Generate illustration
        art = None
        if image_prompt:
            gen_w = min(512, w)
            gen_h = min(384, int(h * 0.62))
            art = _generate_civitai_image(image_prompt, gen_w, gen_h)

        return _compose(motto, art, w, h)
