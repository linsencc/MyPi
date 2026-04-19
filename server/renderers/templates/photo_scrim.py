"""Shared full-bleed photo fit, bottom gradient scrim, and remote image download."""

from __future__ import annotations

import io
import logging
import os
import time
import urllib.request

from PIL import Image, ImageDraw, ImageEnhance

log = logging.getLogger(__name__)


def build_remote_image_opener() -> urllib.request.OpenerDirector:
    """Honor HTTP(S)_PROXY / NO_PROXY like curl so Pi networks that need a proxy can fetch images."""
    proxies = urllib.request.getproxies()
    if proxies:
        return urllib.request.build_opener(urllib.request.ProxyHandler(proxies))
    return urllib.request.build_opener()


DEFAULT_IMAGE_UA = (
    "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
)

# Dark blue-gray scrim base (light text + dark stroke read well).
SCRIM_RGB = (22, 26, 36)


def to_full_color_rgb(img: Image.Image) -> Image.Image:
    """Full RGB; optional slight color boost for washed panels (MYPI_MOTTO_COLOR_BOOST)."""
    rgb = img.convert("RGB")
    raw = os.environ.get("MYPI_MOTTO_COLOR_BOOST", "1.15").strip()
    try:
        factor = float(raw)
    except ValueError:
        factor = 1.15
    if factor > 1.01 and factor <= 2.0:
        rgb = ImageEnhance.Color(rgb).enhance(factor)
    return rgb


def infer_fetch_size(canvas_w: int, canvas_h: int) -> tuple[int, int]:
    """Same aspect as frame, long edge capped (MYPI_MOTTO_FETCH_MAX_SIDE)."""
    max_side = int(os.environ.get("MYPI_MOTTO_FETCH_MAX_SIDE", "2400"))
    max_side = max(400, min(max_side, 8192))
    cw, ch = max(1, canvas_w), max(1, canvas_h)
    if max(cw, ch) <= max_side:
        return cw, ch
    if cw >= ch:
        gen_w = max_side
        gen_h = max(1, int(round(gen_w * ch / cw)))
    else:
        gen_h = max_side
        gen_w = max(1, int(round(gen_h * cw / ch)))
    return max(400, gen_w), max(400, gen_h)


def fit_image_cover(src: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Center-crop and resize to fill target area exactly."""
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


def overlay_bottom_scrim(
    canvas: Image.Image,
    y_start: int,
    fade_h: int,
    *,
    scrim_rgb: tuple[int, int, int] = SCRIM_RGB,
    max_opacity_env: str = "MYPI_MOTTO_SCRIM_MAX",
    default_max_opacity: float = 0.76,
) -> None:
    """Vertical gradient from transparent at top of strip to dark at bottom."""
    raw = os.environ.get(max_opacity_env, str(default_max_opacity)).strip()
    try:
        max_opacity = float(raw)
    except ValueError:
        max_opacity = default_max_opacity
    max_opacity = max(0.38, min(0.92, max_opacity))
    w = canvas.width
    strip = Image.new("RGB", (w, fade_h), scrim_rgb)
    mask = Image.new("L", (w, fade_h))
    draw_mask = ImageDraw.Draw(mask)
    for y in range(fade_h):
        t = y / fade_h if fade_h else 0.0
        alpha = int(255 * max_opacity * (t**1.38))
        draw_mask.line([(0, y), (w - 1, y)], fill=alpha)
    canvas.paste(strip, (0, y_start), mask=mask)


def _socket_timeout(
    timeout: int | tuple[float, float] | None,
    default_if_none: int = 60,
) -> float | tuple[float, float]:
    """Preferred (connect, read) split for callers that support it; see _urllib_open_timeout."""
    if timeout is None:
        raw = os.environ.get("MYPI_REMOTE_IMAGE_TIMEOUT", str(default_if_none)).strip()
        try:
            timeout = max(15, int(raw))
        except ValueError:
            timeout = default_if_none
    if isinstance(timeout, tuple) and len(timeout) == 2:
        return (float(timeout[0]), float(timeout[1]))
    ts = float(timeout)
    connect = max(5.0, min(14.0, ts * 0.32))
    read = max(10.0, ts - connect)
    return (connect, read)


def _urllib_open_timeout(sock_to: float | tuple[float, float]) -> float:
    """Python 3.13+ http.client passes timeout to socket.settimeout(), which must be a float, not a tuple."""
    if isinstance(sock_to, tuple) and len(sock_to) == 2:
        return float(sock_to[0]) + float(sock_to[1])
    return float(sock_to)


def download_image_url(
    url: str,
    opener: urllib.request.OpenerDirector,
    timeout: int | tuple[float, float] | None = None,
    *,
    log_prefix: str = "photo_scrim",
    user_agent: str | None = None,
    retries: int = 3,
    retry_delay_s: float = 2.0,
) -> Image.Image | None:
    sock_to = _socket_timeout(timeout, 60)
    retries = max(1, retries)
    ua = (user_agent or "").strip() or DEFAULT_IMAGE_UA
    req = urllib.request.Request(url, headers={"User-Agent": ua}, method="GET")
    for attempt in range(retries):
        try:
            with opener.open(req, timeout=_urllib_open_timeout(sock_to)) as resp:
                img_data = resp.read()
            # Commons full-resolution art can exceed PIL's default decompression limit.
            _old_limit = Image.MAX_IMAGE_PIXELS
            try:
                Image.MAX_IMAGE_PIXELS = None
                im = Image.open(io.BytesIO(img_data))
            finally:
                Image.MAX_IMAGE_PIXELS = _old_limit
            if im.mode not in ("RGB", "RGBA"):
                im = im.convert("RGBA") if "A" in im.mode else im.convert("RGB")
            return to_full_color_rgb(im.convert("RGB"))
        except Exception as exc:
            if attempt + 1 < retries:
                log.info(
                    "%s: download attempt %s/%s failed; retrying url=%s err=%s",
                    log_prefix,
                    attempt + 1,
                    retries,
                    url[:120],
                    exc,
                )
                time.sleep(retry_delay_s * (1.4**attempt))
            else:
                log.warning(
                    "%s: image download failed after %s attempts url=%s err=%s",
                    log_prefix,
                    retries,
                    url[:120],
                    exc,
                )
    return None
