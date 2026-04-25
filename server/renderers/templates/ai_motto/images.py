"""Keyword → Pinterest (default) → RGB art; optional stock fallbacks; offline gradient.

By default only Pinterest is used for remote art. Set ``MYPI_MOTTO_STOCK_FALLBACK=1`` to
re-enable LoremFlickr / Picsum when Pinterest has no token or returns no usable image.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps, ImageStat

from .net import build_motto_image_opener
from renderers.templates.photo_scrim import download_image_url, to_full_color_rgb

log = logging.getLogger(__name__)

_PINTEREST_UA = "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"


def _stock_fallback_enabled() -> bool:
    """LoremFlickr / Picsum only when explicitly enabled (default: Pinterest-only)."""
    v = os.environ.get("MYPI_MOTTO_STOCK_FALLBACK", "").strip().lower()
    return v in ("1", "true", "yes", "on")

# Glue words / meta-terms to skip when turning LLM English into short search tags (keep landscape nouns).
_TAG_STOPWORDS = frozenset({
    "with", "from", "that", "this", "than", "into", "over", "upon", "under", "above",
    "between", "through", "during", "before", "after", "around", "across", "against",
    "style", "styles", "detailed", "beautiful", "soft", "gentle",
    "light", "lights", "shadow", "shadows",
    "mood", "moody", "atmospheric", "dreamy",
    "masterpiece", "quality", "highly", "very", "much", "more", "most", "some", "such",
    "like", "also", "only", "just", "even", "still", "well", "both", "each", "every",
    "foreground", "background", "middle", "distance", "layered", "layers", "clear", "sharp",
    "full", "color", "colorful", "colour", "vivid", "rich", "bright", "vertical", "portrait",
    "composition", "cinematic", "photography", "photo", "realistic",
    "impressionist", "pastel", "film", "grain", "bokeh",
    "studio", "wash", "sumi", "monochrome", "sepia",
    "wallpaper", "wallpapers", "desktop", "laptop", "aesthetic",
})


def tags_from_image_prompt(prompt: str) -> str:
    """Comma-separated keywords from the English image prompt (also used for Pinterest search)."""
    words = re.findall(r"[a-zA-Z]{4,}", prompt.lower())
    picked: list[str] = []
    seen: set[str] = set()
    for w in words:
        if w in _TAG_STOPWORDS or w in seen:
            continue
        seen.add(w)
        picked.append(w)
        if len(picked) >= 6:
            break
    if not picked:
        return "anime,landscape,scenic,wallpaper,watercolor"
    return ",".join(picked)


def pinterest_search_query_from_tags(tags_csv: str) -> str:
    """Partner search: align with desktop wallpaper / anime scenery mood boards."""
    parts = [t.strip() for t in tags_csv.split(",") if t.strip()]
    base = " ".join(parts[:5]) if parts else "scenic landscape nature anime"
    return (
        f"{base} "
        "anime scenery wallpaper desktop wallpaper aesthetic art "
        "desktop wallpaper illustration watercolor painterly "
        "ghibli inspired landscape cozy village mountain lake "
        "picturesque dreamy atmospheric colorful vibrant "
        "digital painting aesthetic landscape wallpaper laptop"
    )


def _merge_board_pins_first(
    opener: urllib.request.OpenerDirector,
    token: str,
    board_id: str,
    seen: set[str],
    out: list[dict],
) -> None:
    """Append pins from a board (with one bookmark page), deduped by id."""
    bq = urllib.parse.urlencode({"page_size": "50"})
    board = _pinterest_api_get(
        f"/boards/{urllib.parse.quote(board_id, safe='')}/pins?{bq}",
        opener,
        token,
    )
    if not isinstance(board, dict):
        return
    items = board.get("items")
    if isinstance(items, list):
        for p in items:
            if not isinstance(p, dict):
                continue
            pid = p.get("id")
            key = str(pid) if pid is not None else ""
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            out.append(p)
    bm = board.get("bookmark")
    if bm and isinstance(bm, str):
        bq2 = urllib.parse.urlencode({"page_size": "50", "bookmark": bm})
        board2 = _pinterest_api_get(
            f"/boards/{urllib.parse.quote(board_id, safe='')}/pins?{bq2}",
            opener,
            token,
        )
        if isinstance(board2, dict):
            items2 = board2.get("items")
            if isinstance(items2, list):
                for p in items2:
                    if not isinstance(p, dict):
                        continue
                    pid = p.get("id")
                    key = str(pid) if pid is not None else ""
                    if key and key in seen:
                        continue
                    if key:
                        seen.add(key)
                    out.append(p)


def pinterest_access_token() -> str:
    return (
        os.environ.get("MYPI_PINTEREST_ACCESS_TOKEN", "").strip()
        or os.environ.get("PINTEREST_ACCESS_TOKEN", "").strip()
    )


def _pinterest_api_get(
    path_query: str,
    opener: urllib.request.OpenerDirector,
    token: str,
    timeout: int = 30,
) -> dict | list | None:
    """GET https://api.pinterest.com/v5/... with Bearer token."""
    url = f"https://api.pinterest.com/v5{path_query}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": _PINTEREST_UA,
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read()
        return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")[:800]
        except Exception:
            pass
        log.warning(
            "ai_motto: Pinterest API HTTP %s %s body_prefix=%r",
            exc.code,
            path_query[:120],
            body[:400],
        )
        return None
    except Exception as exc:
        log.warning("ai_motto: Pinterest API request failed %s %s", path_query[:120], exc)
        return None


def best_pinterest_image_url(pin: dict) -> str | None:
    """Pick the largest raster URL from pin media.images."""
    media = pin.get("media") or {}
    images = media.get("images") or {}
    if not isinstance(images, dict):
        return None
    best_url = None
    best_px = 0
    for img in images.values():
        if not isinstance(img, dict):
            continue
        url = img.get("url")
        if not url:
            continue
        w = int(img.get("width") or 0)
        h = int(img.get("height") or 0)
        px = w * h
        if px >= best_px:
            best_px = px
            best_url = url
    return best_url


def enrich_pin_if_needed(
    pin: dict, opener: urllib.request.OpenerDirector, token: str
) -> dict:
    """If search summary lacks media.images, fetch full pin by id."""
    if best_pinterest_image_url(pin):
        return pin
    pid = pin.get("id")
    if not pid:
        return pin
    full = _pinterest_api_get(f"/pins/{urllib.parse.quote(str(pid), safe='')}", opener, token)
    return full if isinstance(full, dict) else pin


def collect_pinterest_pin_candidates(
    opener: urllib.request.OpenerDirector,
    token: str,
    search_term: str,
    board_id: str | None,
) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()

    if board_id:
        _merge_board_pins_first(opener, token, board_id, seen, out)
        if not out:
            log.warning(
                "ai_motto: Pinterest board %s returned no pins (check id & token scopes)",
                board_id[:16],
            )

    cc = (os.environ.get("MYPI_PINTEREST_COUNTRY", "US").strip() or "US").upper()[:2]
    limit = min(50, int(os.environ.get("MYPI_PINTEREST_SEARCH_LIMIT", "25")))
    q = urllib.parse.urlencode({"term": search_term, "country_code": cc, "limit": str(limit)})
    partner = _pinterest_api_get(f"/search/partner/pins?{q}", opener, token)
    if isinstance(partner, dict):
        items = partner.get("items")
        if isinstance(items, list):
            for p in items:
                if not isinstance(p, dict):
                    continue
                pid = p.get("id")
                key = str(pid) if pid is not None else ""
                if key and key in seen:
                    continue
                if key:
                    seen.add(key)
                out.append(p)
        bm = partner.get("bookmark")
        if bm and isinstance(bm, str) and len(out) < limit * 2:
            q2 = urllib.parse.urlencode({
                "term": search_term,
                "country_code": cc,
                "limit": str(limit),
                "bookmark": bm,
            })
            partner2 = _pinterest_api_get(f"/search/partner/pins?{q2}", opener, token)
            if isinstance(partner2, dict):
                items2 = partner2.get("items")
                if isinstance(items2, list):
                    for p in items2:
                        if not isinstance(p, dict):
                            continue
                        pid = p.get("id")
                        key = str(pid) if pid is not None else ""
                        if key and key in seen:
                            continue
                        if key:
                            seen.add(key)
                        out.append(p)

    if not out and board_id:
        log.warning("ai_motto: no Pinterest pins after board + partner search")

    return out


def _picsum_seed_per_render(motto: str, tags: str) -> str:
    """New seed every render so Picsum is not stuck on one image per day."""
    h = hashlib.sha256(f"{time.time_ns()}:{tags}:{motto[:120]}".encode()).hexdigest()[:24]
    return f"mypi-{h}"


def rgb_looks_grayscale_photo(img: Image.Image) -> bool:
    """True if the image looks monochrome (do not use as 每日寄语配图)."""
    rgb = img.convert("RGB")
    if rgb.width * rgb.height > 800_000:
        rgb = rgb.resize(
            (max(1, rgb.width // 2), max(1, rgb.height // 2)),
            Image.LANCZOS,
        )
    r, g, b = ImageStat.Stat(rgb).mean[:3]
    spread = max(abs(r - g), abs(r - b), abs(g - b))
    return spread < 6.0


def beautify_landscape_art(img: Image.Image) -> Image.Image:
    """Mild contrast + saturation so wallpapers read richer on e-ink (cheap on Pi)."""
    v = os.environ.get("MYPI_MOTTO_BEAUTIFY", "1").strip().lower()
    if v in ("0", "false", "no", "off"):
        return img
    rgb = img.convert("RGB")
    rgb = ImageEnhance.Contrast(rgb).enhance(1.06)
    rgb = ImageEnhance.Color(rgb).enhance(1.05)
    return rgb


def fetch_pinterest_motto_image(image_prompt: str, motto: str) -> Image.Image | None:
    token = pinterest_access_token()
    if not token:
        log.warning(
            "ai_motto: MYPI_PINTEREST_ACCESS_TOKEN not set; cannot use Pinterest"
        )
        return None

    tags = tags_from_image_prompt(image_prompt)
    term = pinterest_search_query_from_tags(tags)
    opener = build_motto_image_opener()
    board_id = os.environ.get("MYPI_PINTEREST_BOARD_ID", "").strip() or None

    pins = collect_pinterest_pin_candidates(opener, token, term, board_id)
    if not pins:
        log.warning("ai_motto: Pinterest returned no pin candidates for term=%r", term[:80])
        return None

    rng = random.Random(time.time_ns())
    pins_try = pins[:]
    rng.shuffle(pins_try)

    for pin in pins_try:
        pin = enrich_pin_if_needed(pin, opener, token)
        url = best_pinterest_image_url(pin)
        if not url:
            continue
        log.info("ai_motto: Pinterest image candidate pin=%s", str(pin.get("id", ""))[:20])
        img = download_image_url(url, opener, log_prefix="ai_motto")
        if img is None:
            continue
        if rgb_looks_grayscale_photo(img):
            log.info("ai_motto: skipped grayscale Pinterest image, trying next pin")
            continue
        return img

    log.warning("ai_motto: no Pinterest image downloaded after trying %d pins", len(pins))
    return None


def fetch_loremflickr_fallback(
    image_prompt: str, width: int, height: int, motto: str
) -> Image.Image | None:
    tags = tags_from_image_prompt(image_prompt)
    opener = build_motto_image_opener()
    path = urllib.parse.quote(tags, safe=",")
    log.info("ai_motto: fallback loremflickr tags=%r %dx%d", tags, width, height)
    for attempt in range(12):
        bust = time.time_ns() ^ attempt
        lf_url = f"https://loremflickr.com/g/{width}/{height}/{path}?random={bust}"
        img = download_image_url(lf_url, opener, log_prefix="ai_motto")
        if img is None:
            continue
        if rgb_looks_grayscale_photo(img):
            log.info("ai_motto: loremflickr grayscale frame, retry %s/12", attempt + 1)
            continue
        return img
    log.warning("ai_motto: loremflickr exhausted; trying Picsum with color-only retries")
    for attempt in range(24):
        seed = _picsum_seed_per_render(f"{motto}:{attempt}:{time.time_ns()}", tags)
        url = f"https://picsum.photos/seed/{urllib.parse.quote(seed, safe='')}/{width}/{height}"
        img = download_image_url(url, opener, log_prefix="ai_motto")
        if img is None:
            continue
        if rgb_looks_grayscale_photo(img):
            log.info("ai_motto: picsum grayscale, retry %s/24", attempt + 1)
            continue
        return img
    log.warning("ai_motto: no color image found (all sources looked B&W); text-only layout")
    return None


def fetch_web_motto_image(
    image_prompt: str, width: int, height: int, motto: str
) -> Image.Image | None:
    """Pinterest only by default; optional LoremFlickr / Picsum via MYPI_MOTTO_STOCK_FALLBACK."""
    art = fetch_pinterest_motto_image(image_prompt, motto)
    if art is not None:
        return art
    if not _stock_fallback_enabled():
        log.info(
            "ai_motto: Pinterest yielded no image; stock fallback disabled "
            "(set MYPI_MOTTO_STOCK_FALLBACK=1 to allow LoremFlickr/Picsum)"
        )
        return None
    return fetch_loremflickr_fallback(image_prompt, width, height, motto)


def offline_motto_art(gen_w: int, gen_h: int) -> Image.Image:
    """When remote hosts are unreachable, still show a full-bleed background (no network)."""
    raw = os.environ.get("MYPI_MOTTO_OFFLINE_IMAGE", "").strip()
    if raw:
        p = Path(raw)
        if p.is_file():
            try:
                with Image.open(p) as im:
                    return to_full_color_rgb(im.convert("RGB"))
            except OSError as exc:
                log.warning("ai_motto: MYPI_MOTTO_OFFLINE_IMAGE unreadable: %s", exc)
    gw, gh = max(1, gen_w), max(1, gen_h)
    grad = Image.linear_gradient("L").transpose(Image.ROTATE_90).resize((gw, gh))
    return ImageOps.colorize(grad, (28, 36, 52), (232, 218, 200)).convert("RGB")
