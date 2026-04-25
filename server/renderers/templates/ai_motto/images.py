"""Remote art for 每日寄语: Pinscrape only; failure → template uses ``offline_motto_art``.

Pinscrape: ``MYPI_MOTTO_PINSCRAPE`` (set ``0``/``off`` to skip and use offline only), ``MYPI_PINSCRAPE_*``,
``MYPI_LLM_PROXY`` / ``HTTPS_PROXY`` for requests (see ``net.http_proxy_url``).
Offline: ``MYPI_MOTTO_OFFLINE_IMAGE``. Images honor ``MYPI_MOTTO_IMAGE_NO_PROXY`` via ``build_motto_image_opener``.
"""

from __future__ import annotations

import contextlib
import logging
import os
import random
import re
import time
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps, ImageStat

from .net import build_motto_image_opener, http_proxy_url
from renderers.templates.photo_scrim import download_image_url, to_full_color_rgb

log = logging.getLogger(__name__)

_PINSCRAPE_IMPORT_OK: bool | None = None

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
    """Comma-separated keywords from the English image prompt (used to build pinscrape queries)."""
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


def _pinscrape_import_ok() -> bool:
    """Whether optional dependency pinscrape can be imported (cached)."""
    global _PINSCRAPE_IMPORT_OK
    if _PINSCRAPE_IMPORT_OK is not None:
        return _PINSCRAPE_IMPORT_OK
    try:
        import pinscrape  # noqa: F401

        _PINSCRAPE_IMPORT_OK = True
    except Exception:
        _PINSCRAPE_IMPORT_OK = False
    return _PINSCRAPE_IMPORT_OK


def _pinscrape_should_try() -> bool:
    """Unless MYPI_MOTTO_PINSCRAPE is off, try pinscrape when the package is installed."""
    raw = os.environ.get("MYPI_MOTTO_PINSCRAPE", "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    return _pinscrape_import_ok()


def _requests_proxies_for_pinscrape() -> dict[str, str]:
    p = http_proxy_url()
    if not p:
        return {}
    return {"http": p, "https": p}


@contextlib.contextmanager
def _pinscrape_workdir():
    """pinscrape writes ./data/time_epoch.json relative to cwd; isolate under MYPI_PINSCRAPE_DATA_DIR."""
    root = os.environ.get("MYPI_PINSCRAPE_DATA_DIR", "").strip() or "/tmp/mypi-pinscrape"
    os.makedirs(root, exist_ok=True)
    prev = os.getcwd()
    os.chdir(root)
    try:
        yield
    finally:
        os.chdir(prev)


@contextlib.contextmanager
def _pinscrape_proxy_env(proxies: dict[str, str]):
    """pinscrape's first session.get omits proxies=; requests still honors HTTP(S)_PROXY in the environment."""
    if not proxies:
        yield
        return
    keys = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy")
    saved = {k: os.environ.get(k) for k in keys}
    try:
        os.environ["HTTP_PROXY"] = proxies["http"]
        os.environ["HTTPS_PROXY"] = proxies["https"]
        os.environ["http_proxy"] = proxies["http"]
        os.environ["https_proxy"] = proxies["https"]
        yield
    finally:
        for k in keys:
            v = saved.get(k)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _pinscrape_search_query_tags(image_prompt: str) -> str:
    """Short tag-led query for Pinterest web search via pinscrape."""
    tags = tags_from_image_prompt(image_prompt)
    parts = [t.strip() for t in tags.split(",") if t.strip()][:7]
    base = " ".join(parts) if parts else "anime landscape scenic"
    extra = os.environ.get("MYPI_PINSCRAPE_QUERY_SUFFIX", "").strip()
    if extra:
        q = f"{base} {extra}".strip()
    else:
        q = f"{base} landscape painting illustration wallpaper art"
    if len(q) > 200:
        q = q[:197] + "..."
    return q


def _pinscrape_search_query_from_llm_prompt(image_prompt: str) -> str:
    """Second pass: more of the LLM English prompt (nouns/adjectives), still web-search friendly."""
    words = re.findall(r"[a-zA-Z]{3,}", (image_prompt or "").lower())
    picked: list[str] = []
    seen: set[str] = set()
    for w in words:
        if w in _TAG_STOPWORDS or w in seen:
            continue
        seen.add(w)
        picked.append(w)
        if len(picked) >= 12:
            break
    if not picked:
        return ""
    q = " ".join(picked) + " landscape wallpaper art"
    if len(q) > 200:
        q = q[:197] + "..."
    return q


def _pinscrape_query_variants(image_prompt: str) -> list[str]:
    """Ordered search phrases; stop at MYPI_PINSCRAPE_MAX_QUERIES."""
    try:
        nmax = max(1, min(4, int(os.environ.get("MYPI_PINSCRAPE_MAX_QUERIES", "2"))))
    except ValueError:
        nmax = 2
    candidates = (
        _pinscrape_search_query_tags(image_prompt),
        _pinscrape_search_query_from_llm_prompt(image_prompt),
        "anime scenic landscape illustration wallpaper watercolor",
    )
    seen: set[str] = set()
    out: list[str] = []
    for q in candidates:
        q = (q or "").strip()
        if len(q) < 4:
            continue
        k = q.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(q)
        if len(out) >= nmax:
            break
    return out


def _fetch_via_pinscrape(image_prompt: str, _motto: str) -> Image.Image | None:
    """Pinterest image URLs via pinscrape (requests); download via urllib opener (proxy-aware)."""
    if not _pinscrape_import_ok():
        log.warning("ai_motto: pinscrape not installed; pip install pinscrape (see requirements-pinscrape.txt)")
        return None
    from pinscrape import Pinterest

    sleep_raw = os.environ.get("MYPI_PINSCRAPE_SLEEP", "2").strip()
    try:
        sleep_time = max(1.0, float(sleep_raw))
    except ValueError:
        sleep_time = 2.0
    try:
        page_size = max(6, min(50, int(os.environ.get("MYPI_PINSCRAPE_PAGE_SIZE", "20"))))
    except ValueError:
        page_size = 20

    proxies = _requests_proxies_for_pinscrape()
    queries = _pinscrape_query_variants(image_prompt)
    if not queries:
        log.warning("ai_motto: pinscrape has no search queries from prompt")
        return None

    urls: list = []
    try:
        with _pinscrape_workdir(), _pinscrape_proxy_env(proxies):
            p = Pinterest(proxies=proxies or {}, sleep_time=sleep_time)
            for qi, kw in enumerate(queries):
                log.info("ai_motto: pinscrape search[%d] query=%r", qi, kw[:120])
                try:
                    urls = p.search(kw, page_size)
                except Exception as exc:
                    log.warning("ai_motto: pinscrape search[%d] failed: %s", qi, exc)
                    urls = []
                if urls:
                    break
    except Exception as exc:
        log.warning("ai_motto: pinscrape session failed: %s", exc)
        return None

    if not urls:
        log.warning("ai_motto: pinscrape returned no URLs after %d query variant(s)", len(queries))
        return None

    opener = build_motto_image_opener()
    rng = random.Random(time.time_ns())
    urls_try = list(urls)
    rng.shuffle(urls_try)
    pin_headers = {"Referer": "https://www.pinterest.com/", "Accept": "image/avif,image/webp,*/*;q=0.8"}

    for url in urls_try:
        if not url:
            continue
        url_s = url if isinstance(url, str) else str(url)
        log.info("ai_motto: pinscrape image candidate url=%s", url_s[:120])
        img = download_image_url(
            url_s,
            opener,
            log_prefix="ai_motto",
            request_headers=pin_headers,
        )
        if img is None:
            continue
        if rgb_looks_grayscale_photo(img):
            log.info("ai_motto: skipped grayscale pinscrape image, trying next url")
            continue
        return img

    log.warning("ai_motto: no pinscrape image downloaded after trying %d urls", len(urls_try))
    return None


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


def fetch_web_motto_image(
    image_prompt: str,
    _width: int,
    _height: int,
    _motto: str,
) -> Image.Image | None:
    """Pinscrape only; width/height kept for call-site compatibility (offline sizing uses same values in template). On failure return ``None`` — template uses ``offline_motto_art``."""
    if not _pinscrape_should_try():
        flag = os.environ.get("MYPI_MOTTO_PINSCRAPE", "").strip().lower()
        if flag in ("0", "false", "no", "off"):
            log.info("ai_motto: pinscrape disabled (MYPI_MOTTO_PINSCRAPE); using offline wallpaper")
        else:
            log.info("ai_motto: pinscrape not installed; using offline wallpaper (pip install pinscrape)")
        return None
    return _fetch_via_pinscrape(image_prompt, _motto)


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
