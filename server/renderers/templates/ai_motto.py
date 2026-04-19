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
  MYPI_CIVITAI_MODEL    – Civitai model URN (default: DreamShaper XL Lightning)
  MYPI_CIVITAI_TIMEOUT  – Civitai poll timeout seconds (default: 90)
  MYPI_CIVITAI_NO_PROXY – if 1/true: call Civitai without HTTP(S) proxy (LLM may still use proxy)
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
from renderers.templates.cjk_font import _load_cjk_font, _wrap_lines

log = logging.getLogger(__name__)

# ── LLM config ──────────────────────────────────────────────────────
_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_MODEL = "deepseek/deepseek-chat-v3.1"
_DEFAULT_TIMEOUT = 20

_SYSTEM_PROMPT = textwrap.dedent("""\
    你是一位每天陪伴用户的智慧伙伴。请生成以下两项内容，以纯 JSON 返回：

    {
      "motto": "一句中文寄语",
      "image_prompt": "an English image description for SDXL"
    }

    严格要求：
    - 只输出上述 JSON，不加任何其他内容、标签或解释
    - motto: 质朴有深度的中文寄语，40 字以内，不说空话套话，不打招呼
    - image_prompt: 一段描述性的英文画面 prompt，与寄语意境吻合，要求：
      * 主体是自然风景（山川、湖泊、森林、花田、海岸、星空等）
      * 明确指定一种画风，从以下任选：
        impressionist oil painting / watercolor wash / Studio Ghibli anime style /
        ink wash sumi-e / soft pastel illustration / cinematic photography
      * 注重光影描写（golden hour, misty dawn, moonlit, dappled sunlight 等）
      * 构图清晰，前景+中景+远景层次分明
      * 绝对不要出现文字、人脸、画框
      * 控制在 40-60 词
""")

_USER_PROMPT = "请给我今天的一句话和匹配的画面。"

# ── Civitai config ──────────────────────────────────────────────────
_CIVITAI_API = "https://orchestration.civitai.com"
_DEFAULT_CIVITAI_MODEL = "urn:air:sdxl:checkpoint:civitai:112902@354657"
_CIVITAI_POLL_INTERVAL = 4
_CIVITAI_TIMEOUT = 90

# Match civitai-javascript OpenAPI client (request.ts): Accept application/json;
# errors may be application/problem+json (RFC 7807) with a "detail" field.
_CIVITAI_JSON_HEADERS = {
    "Accept": "application/json",
}


def _civitai_http_error_log(exc: urllib.error.HTTPError, what: str) -> None:
    body = ""
    try:
        body = exc.read().decode("utf-8", errors="replace")[:1200]
    except Exception:
        pass
    hdrs = getattr(exc, "headers", None)
    safe: dict[str, str] = {}
    if hdrs is not None:
        for key in ("Content-Type", "Content-Length", "CF-Ray", "X-Request-Id", "Server", "Date"):
            v = hdrs.get(key)
            if v:
                safe[key] = v
    log.warning(
        "ai_motto: Civitai %s HTTP %s reason=%r headers=%s body_len=%s body_prefix=%r",
        what,
        exc.code,
        exc.reason,
        safe,
        (hdrs.get("Content-Length") or "-") if hdrs else "-",
        body[:500] if body else "",
    )


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


def _civitai_opener() -> urllib.request.OpenerDirector:
    """Civitai may need a direct route while the LLM still uses MYPI_LLM_PROXY."""
    v = os.environ.get("MYPI_CIVITAI_NO_PROXY", "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return urllib.request.build_opener()
    return _build_opener()


def _parse_llm_json_blob(raw: str) -> dict | None:
    """Parse JSON object from model output; tolerate fences and leading/trailing text."""
    cleaned = _re.sub(r"```json\s*|\s*```", "", raw).strip()
    try:
        data = json.loads(cleaned)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    dec = json.JSONDecoder()
    for i, ch in enumerate(cleaned):
        if ch != "{":
            continue
        try:
            obj, _end = dec.raw_decode(cleaned, i)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and any(
            k in obj for k in ("motto", "image_prompt", "imagePrompt")
        ):
            return obj
    return None


def _image_prompt_from_data(data: dict) -> str | None:
    v = data.get("image_prompt")
    if v is None or (isinstance(v, str) and not v.strip()):
        v = data.get("imagePrompt")
    if v is None:
        return None
    s = str(v).strip()
    return s or None


# ── LLM call ────────────────────────────────────────────────────────

def _call_llm() -> tuple[str, str | None]:
    """Returns (motto, image_prompt). image_prompt may be None."""
    api_key = os.environ.get("MYPI_LLM_API_KEY", "").strip()
    if not api_key:
        log.info("ai_motto: MYPI_LLM_API_KEY not set, motto fallback and no image")
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
    raw = ""
    try:
        with opener.open(req, timeout=timeout) as resp:
            body = json.loads(resp.read())
        raw = (body["choices"][0]["message"].get("content") or "").strip()
        log.info("ai_motto: LLM raw %d chars", len(raw))

        data = _parse_llm_json_blob(raw)
        if not data:
            log.warning("ai_motto: LLM response is not valid JSON, no image_prompt")
            text = _strip_thinking(raw)
            return text or _get_fallback(), None

        motto = (data.get("motto") or "").strip()
        image_prompt = _image_prompt_from_data(data)
        if not motto:
            motto = _strip_thinking(raw) or _get_fallback()
        if motto and not image_prompt:
            log.info("ai_motto: LLM returned motto but empty image_prompt; text-only layout")
        return motto, image_prompt
    except KeyError:
        text = _strip_thinking(raw) if raw else None
        log.warning("ai_motto: LLM response missing expected fields")
        return text or _get_fallback(), None
    except Exception as exc:
        log.warning("ai_motto: LLM call failed: %s", exc)
        return _get_fallback(), None


# ── Civitai image generation ────────────────────────────────────────

def _generate_civitai_image(prompt: str, width: int, height: int) -> Image.Image | None:
    token = os.environ.get("CIVITAI_TOKEN", "").strip()
    if not token:
        log.warning(
            "ai_motto: CIVITAI_TOKEN not set; skipping Civitai image (set token on the Pi service env)"
        )
        return None

    model_urn = os.environ.get("MYPI_CIVITAI_MODEL", _DEFAULT_CIVITAI_MODEL).strip()
    poll_timeout = int(os.environ.get("MYPI_CIVITAI_TIMEOUT", str(_CIVITAI_TIMEOUT)))

    is_sdxl = ":sdxl:" in model_urn or ":sdxl1:" in model_urn
    # Match Civitai JS SDK defaults (low steps/cfg for SDXL has caused HTTP 500 on orchestration).
    if is_sdxl:
        full_prompt = f"{prompt}, masterpiece, best quality, highly detailed, no text, no watermark, no frame"
        neg_prompt = "(text, watermark, signature, frame, border, picture frame, deformed, blurry, lowres, ugly, disfigured:1.4)"
    else:
        full_prompt = f"{prompt}, masterpiece, best quality, no text, no watermark"
        neg_prompt = "(text, watermark, signature, frame, border, picture frame, deformed, blurry, lowres:1.4)"
    steps, cfg, clip_skip = 20, 7, 2

    job_payload = json.dumps({
        "$type": "textToImage",
        "model": model_urn,
        "params": {
            "prompt": full_prompt,
            "negativePrompt": neg_prompt,
            "scheduler": "EulerA",
            "steps": steps,
            "cfgScale": cfg,
            "width": width,
            "height": height,
            "clipSkip": clip_skip,
        },
    }).encode()

    opener = _civitai_opener()

    # Submit job
    _UA = "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"

    req = urllib.request.Request(
        f"{_CIVITAI_API}/v1/consumer/jobs",
        data=job_payload,
        headers={
            **_CIVITAI_JSON_HEADERS,
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
    except urllib.error.HTTPError as exc:
        _civitai_http_error_log(exc, "submit")
        return None
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
            headers={
                **_CIVITAI_JSON_HEADERS,
                "Authorization": f"Bearer {token}",
                "User-Agent": _UA,
            },
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
        except urllib.error.HTTPError as exc:
            _civitai_http_error_log(exc, "poll")
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

_BG_COLOR = (250, 248, 243)
_TEXT_COLOR = (30, 32, 36)
_SECONDARY_COLOR = (110, 105, 98)
_SUBTLE_COLOR = (150, 145, 138)
_ACCENT_COLOR = (85, 80, 72)
_DIVIDER_COLOR = (200, 196, 188)


def _infer_gen_size(canvas_w: int, canvas_h: int, *, is_sdxl: bool) -> tuple[int, int]:
    """Size for Civitai: match frame aspect, cap long side (1024 SDXL / 512 SD1.5), multiples of 64."""
    max_side = 1024 if is_sdxl else 512
    cw, ch = max(1, canvas_w), max(1, canvas_h)
    if cw >= ch:
        gen_w = min(cw, max_side)
        gen_h = int(gen_w * ch / cw)
    else:
        gen_h = min(ch, max_side)
        gen_w = int(gen_h * cw / ch)
    gen_w = max(256, (gen_w // 64) * 64)
    gen_h = max(256, (gen_h // 64) * 64)
    return gen_w, gen_h


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


def _overlay_gradient(canvas: Image.Image, y_start: int, fade_h: int,
                      max_opacity: float = 0.96) -> None:
    """Apply an ease-in gradient overlay of _BG_COLOR from y_start downward.

    Uses a power curve (t^1.6) so the top of the gradient is nearly
    invisible while the text zone reaches ~45-50% opacity — enough to
    ensure readability on busy/dark backgrounds while still letting the
    image breathe through.
    """
    w = canvas.width
    bg_strip = Image.new("RGB", (w, fade_h), _BG_COLOR)
    mask = Image.new("L", (w, fade_h))
    draw_mask = ImageDraw.Draw(mask)
    for y in range(fade_h):
        t = y / fade_h
        alpha = int(255 * max_opacity * (t ** 1.6))
        draw_mask.line([(0, y), (w - 1, y)], fill=alpha)
    canvas.paste(bg_strip, (0, y_start), mask=mask)


def _cn_date_str() -> str:
    """Today's date in Chinese, e.g. '四月十九日'."""
    now = datetime.now()
    ms = ["一", "二", "三", "四", "五", "六",
          "七", "八", "九", "十", "十一", "十二"]
    ds = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九"]
    d = now.day
    if d <= 10:
        day = "十" if d == 10 else ds[d]
    elif d < 20:
        day = "十" + ds[d - 10]
    elif d == 20:
        day = "二十"
    elif d < 30:
        day = "二十" + ds[d - 20]
    elif d == 30:
        day = "三十"
    else:
        day = "三十一"
    return f"{ms[now.month - 1]}月{day}日"


def _draw_ornament(draw: ImageDraw.ImageDraw, cx: int, cy: int, scale: float) -> None:
    """Draw a ── ◇ ── ornamental divider."""
    half_w = int(26 * scale)
    gap = int(5 * scale)
    d = max(2, int(2.5 * scale))
    draw.line([(cx - half_w - gap, cy), (cx - gap - 1, cy)], fill=_DIVIDER_COLOR, width=1)
    draw.line([(cx + gap + 1, cy), (cx + half_w + gap, cy)], fill=_DIVIDER_COLOR, width=1)
    draw.polygon([
        (cx, cy - d), (cx + d, cy), (cx, cy + d), (cx - d, cy),
    ], fill=_ACCENT_COLOR)


def _compose(
    motto: str,
    art: Image.Image | None,
    canvas_w: int,
    canvas_h: int,
) -> Image.Image:
    img = Image.new("RGB", (canvas_w, canvas_h), color=_BG_COLOR)
    draw = ImageDraw.Draw(img)
    scale = min(canvas_w, canvas_h) / 600
    cx = canvas_w // 2
    margin = max(32, int(canvas_w * 0.06))

    if art:
        # ── Full-bleed image + gradient overlay ──────────────
        fitted = _fit_image(art, canvas_w, canvas_h)
        img.paste(fitted, (0, 0))

        grad_start = int(canvas_h * 0.45)
        _overlay_gradient(img, grad_start, canvas_h - grad_start)
        draw = ImageDraw.Draw(img)

        # Text sits in the opaque zone (lower ~28%)
        text_zone_center = int(canvas_h * 0.76)
        size_px = max(24, int(34 * scale))
        font = _load_cjk_font(size_px)
        raw_max = max(8, int((canvas_w - margin * 2) / (size_px * 1.05)))
        n = len(motto)
        if n <= raw_max:
            max_chars = n
        elif n <= raw_max * 2:
            max_chars = (n + 1) // 2
        else:
            max_chars = raw_max
        lines = _wrap_lines(motto, max_chars=max_chars, max_lines=4)
        line_h = int(size_px * 1.55)
        block_h = len(lines) * line_h
        y0 = text_zone_center - block_h // 2

        shadow_off = max(1, int(1.5 * scale))
        shadow_color = (180, 178, 174)
        for k, ln in enumerate(lines):
            bbox = draw.textbbox((0, 0), ln, font=font)
            tw = bbox[2] - bbox[0]
            tx = (canvas_w - tw) // 2
            ty = y0 + k * line_h
            draw.text((tx + shadow_off, ty + shadow_off), ln,
                      fill=shadow_color, font=font)
            draw.text((tx, ty), ln, fill=_TEXT_COLOR, font=font)

        # Footer: date + attribution
        footer_y = canvas_h - int(28 * scale)
        small = _load_cjk_font(max(11, int(13 * scale)))
        date_str = _cn_date_str()
        attr_str = "— 每日寄语"
        spacer = int(20 * scale)
        db = draw.textbbox((0, 0), date_str, font=small)
        ab = draw.textbbox((0, 0), attr_str, font=small)
        dw, aw = db[2] - db[0], ab[2] - ab[0]
        total = dw + spacer + aw
        x0 = (canvas_w - total) // 2
        draw.text((x0, footer_y), date_str, fill=_SECONDARY_COLOR, font=small)
        draw.text((x0 + dw + spacer, footer_y), attr_str, fill=_SUBTLE_COLOR, font=small)

    else:
        # ── Text only (no image) ─────────────────────────────
        bar_w = int(40 * scale)
        bar_h = max(2, int(3 * scale))
        bar_y = int(canvas_h * 0.32)
        draw.rectangle(
            [(cx - bar_w // 2, bar_y), (cx + bar_w // 2, bar_y + bar_h)],
            fill=_ACCENT_COLOR,
        )

        size_px = max(30, int(42 * scale))
        font = _load_cjk_font(size_px)
        max_chars = max(6, int((canvas_w - margin * 2) / (size_px * 1.05)))
        lines = _wrap_lines(motto, max_chars=max_chars, max_lines=4)
        line_h = int(size_px * 1.6)
        block_h = len(lines) * line_h
        y0 = bar_y + bar_h + int(24 * scale)

        for k, ln in enumerate(lines):
            bbox = draw.textbbox((0, 0), ln, font=font)
            tw = bbox[2] - bbox[0]
            draw.text(((canvas_w - tw) // 2, y0 + k * line_h), ln,
                      fill=_TEXT_COLOR, font=font)

        text_bottom = y0 + block_h
        div_y = text_bottom + int(22 * scale)
        _draw_ornament(draw, cx, div_y, scale)

        footer_y = div_y + int(18 * scale)
        small = _load_cjk_font(max(11, int(14 * scale)))
        date_str = _cn_date_str()
        attr_str = "— 每日寄语"
        spacer = int(20 * scale)
        db = draw.textbbox((0, 0), date_str, font=small)
        ab = draw.textbbox((0, 0), attr_str, font=small)
        dw, aw = db[2] - db[0], ab[2] - ab[0]
        total = dw + spacer + aw
        x0 = (canvas_w - total) // 2
        draw.text((x0, footer_y), date_str, fill=_SECONDARY_COLOR, font=small)
        draw.text((x0 + dw + spacer, footer_y), attr_str, fill=_SUBTLE_COLOR, font=small)

    return img


# ── Template class ──────────────────────────────────────────────────

class AiMottoTemplate(WallTemplate):
    display_name = "每日寄语"

    def render(self, ctx: RenderContext) -> Image.Image:
        params = ctx.scene.template_params or {}
        w = ctx.device_profile.get("width", 800)
        h = ctx.device_profile.get("height", 600)

        # Override text from params (only non-empty string skips LLM + image)
        raw_ov = params.get("text")
        override_text = raw_ov.strip() if isinstance(raw_ov, str) else ""
        if override_text:
            log.info("ai_motto: templateParams.text set; using fixed motto, no LLM/Civitai image")
            motto, image_prompt = override_text, None
        else:
            motto, image_prompt = _call_llm()

        art = None
        if image_prompt:
            model_urn = os.environ.get("MYPI_CIVITAI_MODEL", _DEFAULT_CIVITAI_MODEL).strip()
            is_sdxl = ":sdxl:" in model_urn or ":sdxl1:" in model_urn
            gen_w, gen_h = _infer_gen_size(w, h, is_sdxl=is_sdxl)
            art = _generate_civitai_image(image_prompt, gen_w, gen_h)

        return _compose(motto, art, w, h)
