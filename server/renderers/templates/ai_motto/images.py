"""Remote art for 每日寄语: optional Pinterest **board** image pool, then Pinscrape keyword search.

Board pool: (1) ``widgets.pinterest.com/v3/pidgets/boards/{user}/{board}/pins/`` — one URL per pin for
nearly the whole board; (2) board **page HTML** parse as a supplement (SSR often only repeats a small
subset of ``orig`` URLs, which caused "always the same few wallpapers" before pidget merge).

Default board ``https://www.pinterest.com/elliotprl/wallpaper/`` — override with ``MYPI_MOTTO_BOARD_URL``.
Pinscrape search: ``MYPI_MOTTO_PINSCRAPE`` (``0``/``off`` skips keyword path only; board uses stdlib urllib).
``MYPI_PINSCRAPE_*``, ``MYPI_LLM_PROXY`` / ``HTTPS_PROXY`` (see ``net.http_proxy_url``).
Offline: ``MYPI_MOTTO_OFFLINE_IMAGE``. Images honor ``MYPI_MOTTO_IMAGE_NO_PROXY`` via ``build_motto_image_opener``.

Note: pinscrape's ``Pinterest.get_pin_details`` does not return image URLs; board pins use pidget JSON + HTML embed.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import random
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

from PIL import Image, ImageEnhance, ImageOps, ImageStat

from .net import build_motto_image_opener, http_proxy_url
from renderers.templates.photo_scrim import download_image_url, to_full_color_rgb

log = logging.getLogger(__name__)

_PINSCRAPE_IMPORT_OK: bool | None = None

# Public board used as default wallpaper pool (see prompts / product spec).
_DEFAULT_MOTTO_BOARD_URL = "https://www.pinterest.com/elliotprl/wallpaper/"
_PINIMG_ORIG_RE = re.compile(
    r"https://i\.pinimg\.com/originals/[^\"'\\s<>]+",
    re.IGNORECASE,
)


def _motto_pinterest_board_url() -> str | None:
    """Board page to scrape for pin CDN URLs. Explicit empty / 0 / off disables."""
    if "MYPI_MOTTO_BOARD_URL" in os.environ:
        v = os.environ["MYPI_MOTTO_BOARD_URL"].strip()
        if not v or v.lower() in ("0", "false", "no", "off"):
            return None
        return _normalize_pinterest_board_url(v)
    return _DEFAULT_MOTTO_BOARD_URL


def _normalize_pinterest_board_url(url: str) -> str:
    u = url.strip().split("?")[0].rstrip("/")
    if not u.startswith("http"):
        u = "https://" + u.lstrip("/")
    return u + "/" if not u.endswith("/") else u


def _board_user_slug_from_pinterest_url(board_url: str) -> tuple[str, str] | None:
    """``username`` and ``board_slug`` from ``…/username/board/…`` (first two path segments after pinterest.com)."""
    u = board_url.strip().split("?")[0].strip()
    low = u.lower()
    key = "pinterest.com"
    if key not in low:
        return None
    i = low.index(key) + len(key)
    tail = u[i:].strip("/")
    parts = [p for p in tail.split("/") if p and p not in ("pin", "ideas", "today")]
    if len(parts) >= 2:
        return parts[0], parts[1]
    return None


def _fetch_pidget_board_pin_image_urls(
    username: str,
    board_slug: str,
    opener: urllib.request.OpenerDirector,
) -> list[str]:
    """Public widget JSON: one image URL per pin (covers almost the full board vs SSR HTML subset)."""
    api = (
        "https://widgets.pinterest.com/v3/pidgets/boards/"
        f"{quote(username, safe='')}/{quote(board_slug, safe='')}/pins/"
    )
    req = urllib.request.Request(
        api,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://www.pinterest.com/",
        },
        method="GET",
    )
    try:
        with opener.open(req, timeout=35) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        log.warning("ai_motto: pidget board pins HTTP %s", exc.code)
        return []
    except Exception as exc:
        log.warning("ai_motto: pidget board pins fetch failed: %s", exc)
        return []
    try:
        j = json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return []
    if j.get("status") != "success":
        return []
    data = j.get("data")
    if not isinstance(data, dict):
        return []
    pins = data.get("pins")
    if not isinstance(pins, list):
        return []
    out: list[str] = []
    for pin in pins:
        if not isinstance(pin, dict):
            continue
        if pin.get("is_video"):
            continue
        images = pin.get("images")
        if not isinstance(images, dict):
            continue
        u: str | None = None
        for key in ("736x", "orig", "564x", "474x", "236x"):
            blob = images.get(key)
            if isinstance(blob, dict):
                cand = blob.get("url")
                if isinstance(cand, str) and "pinimg.com" in cand:
                    u = cand
                    break
        if u:
            out.append(u.strip().split("\\")[0].strip())
    return out


def _merge_pinimg_url_lists(*lists: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for lst in lists:
        for u in lst:
            u2 = u.split("\\")[0].strip()
            if u2 and u2 not in seen:
                seen.add(u2)
                out.append(u2)
    return out


def _collect_orig_urls_from_pinterest_json(obj: object, out: list[str]) -> None:
    """Depth-first walk for pin ``images.orig.url`` blobs in Pinterest Redux JSON."""
    if isinstance(obj, dict):
        if "images" in obj and isinstance(obj["images"], dict):
            orig = obj["images"].get("orig")
            if isinstance(orig, dict):
                u = orig.get("url")
                if isinstance(u, str) and "pinimg.com" in u:
                    out.append(u)
            elif isinstance(orig, list):
                for it in orig:
                    if isinstance(it, dict):
                        u = it.get("url")
                        if isinstance(u, str) and "pinimg.com" in u:
                            out.append(u)
        for v in obj.values():
            _collect_orig_urls_from_pinterest_json(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _collect_orig_urls_from_pinterest_json(v, out)


def _parse_board_html_for_pin_urls(html: str) -> list[str]:
    urls: list[str] = []
    for sid in ("__PWS_INITIAL_PROPS__", "__PWS_DATA__"):
        pat = re.compile(
            rf'<script[^>]*id="{re.escape(sid)}"[^>]*>(.*?)</script>',
            re.DOTALL | re.IGNORECASE,
        )
        for m in pat.finditer(html):
            raw = m.group(1).strip()
            if not raw or raw[0] not in "{[":
                continue
            try:
                j = json.loads(raw)
            except json.JSONDecodeError:
                continue
            _collect_orig_urls_from_pinterest_json(j, urls)
    for u in _PINIMG_ORIG_RE.findall(html):
        urls.append(u)
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        u2 = u.split("\\")[0].strip()
        if u2 and u2 not in seen:
            seen.add(u2)
            out.append(u2)
    return out


def _fetch_pinterest_board_html(board_url: str, opener: urllib.request.OpenerDirector) -> str | None:
    req = urllib.request.Request(
        board_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
        method="GET",
    )
    try:
        with opener.open(req, timeout=40) as resp:
            raw = resp.read()
        if len(raw) > 4_000_000:
            raw = raw[:4_000_000]
        return raw.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        log.warning("ai_motto: board page HTTP %s", exc.code)
        return None
    except Exception as exc:
        log.warning("ai_motto: board page fetch failed: %s", exc)
        return None


def _try_download_pin_urls(urls: list[str], opener: urllib.request.OpenerDirector) -> Image.Image | None:
    if not urls:
        return None
    rng = random.Random(time.time_ns())
    urls_try = list(urls)
    rng.shuffle(urls_try)
    try:
        cap = max(12, min(200, int(os.environ.get("MYPI_MOTTO_MAX_PIN_TRIES", "96"))))
    except ValueError:
        cap = 96
    pin_headers = {"Referer": "https://www.pinterest.com/", "Accept": "image/avif,image/webp,*/*;q=0.8"}
    for url in urls_try[:cap]:
        if not url or "pinimg.com" not in url:
            continue
        log.info("ai_motto: pin candidate url=%s", url[:120])
        img = download_image_url(
            url,
            opener,
            log_prefix="ai_motto",
            request_headers=pin_headers,
        )
        if img is None:
            continue
        if rgb_looks_grayscale_photo(img):
            log.info("ai_motto: skipped grayscale image, trying next url")
            continue
        return img
    return None

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


def _fetch_via_pinscrape(image_prompt: str, opener: urllib.request.OpenerDirector) -> Image.Image | None:
    """Pinterest image URLs via pinscrape ``search()``; download via urllib opener (proxy-aware)."""
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

    urls_try = [str(u) for u in urls if u]
    img = _try_download_pin_urls(urls_try, opener)
    if img is None:
        log.warning("ai_motto: no pinscrape image downloaded after trying %d urls", len(urls_try))
    return img


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
    """Try Pinterest board (pidget JSON + HTML), then pinscrape keyword search. On failure return ``None`` — template uses ``offline_motto_art``."""
    opener = build_motto_image_opener()
    bu = _motto_pinterest_board_url()
    if bu:
        html = _fetch_pinterest_board_html(bu, opener)
        pidget_urls: list[str] = []
        slug = _board_user_slug_from_pinterest_url(bu)
        if slug:
            user, board = slug
            pidget_urls = _fetch_pidget_board_pin_image_urls(user, board, opener)
            log.info(
                "ai_motto: pidget boards/%s/%s → %d pin image urls",
                user,
                board,
                len(pidget_urls),
            )
        html_urls: list[str] = _parse_board_html_for_pin_urls(html) if html else []
        cand = _merge_pinimg_url_lists(pidget_urls, html_urls)
        if cand:
            log.info("ai_motto: board %r → %d merged pinimg candidates", bu[:72], len(cand))
            art = _try_download_pin_urls(cand, opener)
            if art is not None:
                return art
        log.info("ai_motto: board path yielded no usable image; trying pinscrape search")

    if not _pinscrape_should_try():
        flag = os.environ.get("MYPI_MOTTO_PINSCRAPE", "").strip().lower()
        if flag in ("0", "false", "no", "off"):
            log.info("ai_motto: pinscrape disabled (MYPI_MOTTO_PINSCRAPE); using offline wallpaper")
        else:
            log.info("ai_motto: pinscrape not installed; using offline wallpaper (pip install pinscrape)")
        return None
    return _fetch_via_pinscrape(image_prompt, opener)


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
