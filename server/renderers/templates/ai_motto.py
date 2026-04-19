"""AI-generated daily message template with a Pinterest-sourced illustration.

Targets **full-color RGB** for color e-ink. Downloaded photos are rejected if they look **black &
white**; if no color image is found after retries, the layout falls back to **text only** (no art).

Each render:
  1. Calls LLM to generate a Chinese motto + English image prompt (landscape / scenery, any style)
  2. Fetches a full-color landscape image from Pinterest (or fallbacks; see below)
  3. Composes a full-bleed image with text overlay (portrait-friendly, image is cropped to the frame)

Environment variables:
  MYPI_LLM_API_KEY             – OpenAI-compatible API key
  MYPI_LLM_BASE_URL            – API base URL (default: https://api.openai.com/v1)
  MYPI_LLM_MODEL               – Model name (default: deepseek/deepseek-chat-v3.1)
  MYPI_LLM_TIMEOUT             – LLM timeout seconds (default: 20)
  MYPI_LLM_PROXY               – HTTP(S) proxy for LLM calls
  MYPI_PINTEREST_ACCESS_TOKEN  – Pinterest API OAuth access token (or PINTEREST_ACCESS_TOKEN)
  MYPI_PINTEREST_COUNTRY       – ISO 3166-1 alpha-2 for partner search (default: US)
  MYPI_PINTEREST_BOARD_ID      – Optional numeric board id (e.g. your wallpaper moodboard). When set, pins from
                                  this board are loaded first (same account as token), then partner search fills in.
                                  URL pinterest.com/…/wallpaper/ → id from Pinterest API or site JSON, not the slug alone.
  MYPI_MOTTO_FETCH_MAX_SIDE    – Max long edge when downloading (default: 2400; matches frame aspect)
  MYPI_MOTTO_COLOR_BOOST       – PIL Color enhance on the photo layer (default: 1.15 for color e-ink). Set 1.0 to disable.
  MYPI_MOTTO_FONT              – Optional path to .ttf/.otf/.ttc for the quote (literary title font).
  MYPI_MOTTO_FONT_BOLD         – Optional path to a bolder face for the quote; if unset, stroke is used on MYPI_MOTTO_FONT or default CJK.
  MYPI_MOTTO_IMAGE_NO_PROXY      – if 1/true: Pinterest/image HTTP without proxy (LLM may still use proxy)
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import random
import re as _re
import textwrap
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageStat

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
      "image_prompt": "English keywords for landscape wallpaper image search"
    }

    严格要求：
    - 只输出上述 JSON，不加任何其他内容、标签或解释
    - motto（核心）：要有**具体来历或质感**，避免空洞鸡汤与万能句（少用「愿你」「加油」「不负韶华」等套话）。
      优先从下列**类型中选一类**完成（每次一类即可，不要杂糅）：
      * 中外文学名著、作家语录的**短摘**（可带书名，六字内简称即可）
      * 经典**影视/动画台词**（**必须**用《片名》标注来源；避免总是同一大热片）
      * **诗词、古文**一句（可带作者；勿堆砌生僻字）
      * 历史人物、思想家、科学家等**真实语录**（带人名）
      * 近现代杂文、随笔中的**锐利短句**（可带作者）
      若用翻译句，读感要像中文书面语；总长度 **36 字以内**，不打招呼、不写日期。
    - image_prompt: 英文检索用语，用于匹配**全彩「风景壁纸」风**配图（竖屏画框全幅背景 + 底部叠字），与寄语意境相合。
      整体气质参考 Pinterest 上常见的 **scenery wallpaper / desktop wallpaper art** 类收藏：
      * **偏插画与氛围**：水彩/数字绘景、吉卜力式开阔自然、海边小镇、花田、阳台望远、林荫街景等**无人物主体**的风景；
        可与 **anime scenery wallpaper**、**aesthetic landscape illustration**、**cozy village**、**mountain lake** 等语汇同向
      * 也允许偏写实的 **color landscape photography**，但仍要 **壁纸感**（层次、色彩、治愈），不要新闻纪实风
      * 必须 **full color**、**colorful**；禁止黑白、单色、sepia、monochrome、人脸特写、室内生活场景为主体
      * 适合 **vertical / portrait** 或易竖裁的横幅远景；不要画面内文字、画框
      * 控制在 40–60 词
""")

_USER_PROMPT = (
    "请给我今天的一句寄语，以及相配的全彩「风景壁纸风」英文检索用语（偏插画/氛围壁纸，与桌面风景壁纸审美相近）。"
)

# 轮换「侧重」，降低连续几天内容雷同（与 system 中的类型呼应）。
_MOTTO_FOCUS_ROTATION: tuple[str, ...] = (
    "本次请优先：文学摘句或作家金句，可带简称书名。",
    "本次请优先：影视或动画台词，务必带《片名》，勿与常见鸡汤混同。",
    "本次请优先：古诗词或古文一句，可带作者。",
    "本次请优先：哲学家、科学家、史学家等人物短语录，带人名。",
    "本次请优先：近现代杂文、随笔中的句子，带作者。",
    "本次请优先：外国文学汉译名句，可带译者或书名。",
)

# ── Fallbacks ───────────────────────────────────────────────────────
_FALLBACK_MESSAGES = (
    "人生如逆旅，我亦是行人。——苏轼",
    "世上只有一种英雄主义，就是在认清生活真相之后依然热爱生活。——罗曼·罗兰",
    "一个人知道自己为什么而活，就可以忍受任何一种生活。——尼采",
    "我来到这个世界上，为了看看太阳和蓝色的地平线。——巴尔蒙特",
    "路漫漫其修远兮，吾将上下而求索。——屈原",
    "生活不可能像你想象得那么好，但也不会像你想象得那么糟。——莫泊桑",
)


def _get_fallback() -> str:
    i = datetime.now().timetuple().tm_yday % len(_FALLBACK_MESSAGES)
    return _FALLBACK_MESSAGES[i]


# Quote typography: optional env paths, else try common bold CJK, else regular CJK + stroke.
_MOTTO_BOLD_CANDIDATES: tuple[tuple[Path, int], ...] = (
    (Path(r"C:\Windows\Fonts\msyhbd.ttc"), 0),
    (Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"), 0),
    (Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc"), 0),
    (Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"), 0),
)


def _try_truetype(path: Path, size: int, index: int = 0) -> ImageFont.FreeTypeFont | None:
    if not path.is_file():
        return None
    try:
        if path.suffix.lower() == ".ttc":
            return ImageFont.truetype(str(path), size=size, index=index)
        return ImageFont.truetype(str(path), size=size)
    except OSError:
        return None


def _load_motto_quote_font(size: int) -> tuple[ImageFont.FreeTypeFont, bool]:
    """Return (font, has_natural_bold). If False, draw with stroke for legibility on photos."""
    b = os.environ.get("MYPI_MOTTO_FONT_BOLD", "").strip()
    if b:
        f = _try_truetype(Path(b), size)
        if f is not None:
            return f, True
    m = os.environ.get("MYPI_MOTTO_FONT", "").strip()
    if m:
        f = _try_truetype(Path(m), size)
        if f is not None:
            return f, False
    for p, idx in _MOTTO_BOLD_CANDIDATES:
        f = _try_truetype(p, size, index=idx)
        if f is not None:
            return f, True
    return _load_cjk_font(size), False


def _motto_focus_line() -> str:
    """Daily-rotating emphasis so LLM output does not cluster on one source type."""
    now = datetime.now()
    i = (now.timetuple().tm_yday * 7 + now.month * 3 + now.weekday()) % len(_MOTTO_FOCUS_ROTATION)
    return _MOTTO_FOCUS_ROTATION[i]


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


def _motto_image_opener() -> urllib.request.OpenerDirector:
    """Image hosts may need a direct route while the LLM still uses MYPI_LLM_PROXY."""
    v = os.environ.get("MYPI_MOTTO_IMAGE_NO_PROXY", "").strip().lower()
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

    user_content = f"{_USER_PROMPT}\n\n{_motto_focus_line()}"
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
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


# ── Web image fetch (keyword → photo) ───────────────────────────────

_UA = "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"

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
    "composition", "cinematic", "photography", "photo", "realistic", "anime", "illustration",
    "painting", "watercolor", "impressionist", "pastel", "film", "grain", "bokeh",
    "studio", "ghibli", "wash", "sumi", "monochrome", "sepia",
    "wallpaper", "wallpapers", "desktop", "laptop", "aesthetic",
})


def _tags_from_image_prompt(prompt: str) -> str:
    """Comma-separated keywords from the English image prompt (also used for Pinterest search)."""
    words = _re.findall(r"[a-zA-Z]{4,}", prompt.lower())
    picked: list[str] = []
    seen: set[str] = set()
    for w in words:
        if w in _TAG_STOPWORDS or w in seen:
            continue
        seen.add(w)
        picked.append(w)
        if len(picked) >= 4:
            break
    if not picked:
        return "landscape,scenic,mountain,lake"
    return ",".join(picked)


def _pinterest_search_query_from_tags(tags_csv: str) -> str:
    """Partner search: scenery wallpaper / desktop art mood (see user moodboard style)."""
    parts = [t.strip() for t in tags_csv.split(",") if t.strip()]
    base = " ".join(parts[:5]) if parts else "scenic landscape nature"
    return (
        f"{base} scenery wallpaper desktop wallpaper art "
        "anime landscape illustration aesthetic colorful vibrant "
        "nature outdoor digital painting watercolor"
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


def _pinterest_access_token() -> str:
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
            "User-Agent": _UA,
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


def _best_pinterest_image_url(pin: dict) -> str | None:
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


def _pin_maybe_enrich(pin: dict, opener: urllib.request.OpenerDirector, token: str) -> dict:
    """If search summary lacks media.images, fetch full pin by id."""
    if _best_pinterest_image_url(pin):
        return pin
    pid = pin.get("id")
    if not pid:
        return pin
    full = _pinterest_api_get(f"/pins/{urllib.parse.quote(str(pid), safe='')}", opener, token)
    return full if isinstance(full, dict) else pin


def _pinterest_collect_pin_candidates(
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


def _rgb_looks_grayscale_photo(img: Image.Image) -> bool:
    """True if the image looks monochrome (do not use as 每日寄语配图)."""
    rgb = img.convert("RGB")
    if rgb.width * rgb.height > 800_000:
        rgb = rgb.resize(
            (max(1, rgb.width // 2), max(1, rgb.height // 2)),
            Image.LANCZOS,
        )
    r, g, b = ImageStat.Stat(rgb).mean[:3]
    spread = max(abs(r - g), abs(r - b), abs(g - b))
    # Color photos typically have much higher mean channel separation than B&W stock.
    return spread < 6.0


def _to_full_color_rgb(img: Image.Image) -> Image.Image:
    """Full RGB for color e-ink; default slight Color boost for washed panels."""
    rgb = img.convert("RGB")
    raw = os.environ.get("MYPI_MOTTO_COLOR_BOOST", "1.15").strip()
    try:
        factor = float(raw)
    except ValueError:
        factor = 1.15
    if factor > 1.01 and factor <= 2.0:
        rgb = ImageEnhance.Color(rgb).enhance(factor)
    return rgb


def _download_image_url(url: str, opener: urllib.request.OpenerDirector, timeout: int = 45) -> Image.Image | None:
    req = urllib.request.Request(url, headers={"User-Agent": _UA}, method="GET")
    try:
        with opener.open(req, timeout=timeout) as resp:
            img_data = resp.read()
        im = Image.open(io.BytesIO(img_data))
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA") if "A" in im.mode else im.convert("RGB")
        return _to_full_color_rgb(im.convert("RGB"))
    except Exception as exc:
        log.warning("ai_motto: image download failed url=%s err=%s", url[:120], exc)
        return None


def _fetch_pinterest_motto_image(
    image_prompt: str,
    motto: str,
) -> Image.Image | None:
    token = _pinterest_access_token()
    if not token:
        log.warning(
            "ai_motto: MYPI_PINTEREST_ACCESS_TOKEN not set; cannot use Pinterest"
        )
        return None

    tags = _tags_from_image_prompt(image_prompt)
    term = _pinterest_search_query_from_tags(tags)
    opener = _motto_image_opener()
    board_id = os.environ.get("MYPI_PINTEREST_BOARD_ID", "").strip() or None

    pins = _pinterest_collect_pin_candidates(opener, token, term, board_id)
    if not pins:
        log.warning("ai_motto: Pinterest returned no pin candidates for term=%r", term[:80])
        return None

    # Shuffle each render so we don't always pick the same pin when motto/tags repeat same day.
    rng = random.Random(time.time_ns())
    pins_try = pins[:]
    rng.shuffle(pins_try)

    for pin in pins_try:
        pin = _pin_maybe_enrich(pin, opener, token)
        url = _best_pinterest_image_url(pin)
        if not url:
            continue
        log.info("ai_motto: Pinterest image candidate pin=%s", str(pin.get("id", ""))[:20])
        img = _download_image_url(url, opener)
        if img is None:
            continue
        if _rgb_looks_grayscale_photo(img):
            log.info("ai_motto: skipped grayscale Pinterest image, trying next pin")
            continue
        return img

    log.warning("ai_motto: no Pinterest image downloaded after trying %d pins", len(pins))
    return None


def _fetch_loremflickr_fallback(image_prompt: str, width: int, height: int, motto: str) -> Image.Image | None:
    tags = _tags_from_image_prompt(image_prompt)
    opener = _motto_image_opener()
    path = urllib.parse.quote(tags, safe=",")
    log.info("ai_motto: fallback loremflickr tags=%r %dx%d", tags, width, height)
    for attempt in range(12):
        bust = time.time_ns() ^ attempt
        lf_url = f"https://loremflickr.com/g/{width}/{height}/{path}?random={bust}"
        img = _download_image_url(lf_url, opener)
        if img is None:
            continue
        if _rgb_looks_grayscale_photo(img):
            log.info("ai_motto: loremflickr grayscale frame, retry %s/12", attempt + 1)
            continue
        return img
    log.warning("ai_motto: loremflickr exhausted; trying Picsum with color-only retries")
    for attempt in range(24):
        seed = _picsum_seed_per_render(f"{motto}:{attempt}:{time.time_ns()}", tags)
        url = f"https://picsum.photos/seed/{urllib.parse.quote(seed, safe='')}/{width}/{height}"
        img = _download_image_url(url, opener)
        if img is None:
            continue
        if _rgb_looks_grayscale_photo(img):
            log.info("ai_motto: picsum grayscale, retry %s/24", attempt + 1)
            continue
        return img
    log.warning("ai_motto: no color image found (all sources looked B&W); text-only layout")
    return None


def _fetch_web_motto_image(image_prompt: str, width: int, height: int, motto: str) -> Image.Image | None:
    """Pinterest first; optional LoremFlickr if token missing or no pins."""
    art = _fetch_pinterest_motto_image(image_prompt, motto)
    if art is not None:
        return art
    return _fetch_loremflickr_fallback(image_prompt, width, height, motto)


# ── Composition ─────────────────────────────────────────────────────

_BG_COLOR = (250, 248, 243)
_TEXT_COLOR = (30, 32, 36)
_SECONDARY_COLOR = (110, 105, 98)
_SUBTLE_COLOR = (150, 145, 138)
_ACCENT_COLOR = (85, 80, 72)
_DIVIDER_COLOR = (200, 196, 188)
# Full-bleed overlay: warm paper + dark stroke for readability on bright skies.
_QUOTE_FILL_ART = (252, 250, 245)
_QUOTE_STROKE_ART = (28, 30, 36)
_QUOTE_SHADOW_ART = (42, 40, 38)


def _infer_fetch_size(canvas_w: int, canvas_h: int) -> tuple[int, int]:
    """Pixel size for non-Pinterest fallbacks: same aspect as the frame, long edge capped."""
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
        size_px = max(26, int(36 * scale))
        font, quote_bold = _load_motto_quote_font(size_px)
        raw_max = max(8, int((canvas_w - margin * 2) / (size_px * 1.05)))
        n = len(motto)
        if n <= raw_max:
            max_chars = n
        elif n <= raw_max * 2:
            max_chars = (n + 1) // 2
        else:
            max_chars = raw_max
        lines = _wrap_lines(motto, max_chars=max_chars, max_lines=4)
        line_h = int(size_px * 1.52)
        block_h = len(lines) * line_h
        y0 = text_zone_center - block_h // 2

        shadow_off = max(1, int(1.5 * scale))
        stroke_w = 0 if quote_bold else max(1, int(1.8 * scale))
        for k, ln in enumerate(lines):
            bbox = draw.textbbox((0, 0), ln, font=font)
            tw = bbox[2] - bbox[0]
            tx = (canvas_w - tw) // 2
            ty = y0 + k * line_h
            if quote_bold:
                draw.text(
                    (tx + shadow_off, ty + shadow_off),
                    ln,
                    fill=_QUOTE_SHADOW_ART,
                    font=font,
                )
                draw.text((tx, ty), ln, fill=_QUOTE_FILL_ART, font=font)
            else:
                draw.text(
                    (tx, ty),
                    ln,
                    fill=_QUOTE_FILL_ART,
                    font=font,
                    stroke_width=stroke_w,
                    stroke_fill=_QUOTE_STROKE_ART,
                )

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
        font, quote_bold = _load_motto_quote_font(size_px)
        max_chars = max(6, int((canvas_w - margin * 2) / (size_px * 1.05)))
        lines = _wrap_lines(motto, max_chars=max_chars, max_lines=4)
        line_h = int(size_px * 1.58)
        block_h = len(lines) * line_h
        y0 = bar_y + bar_h + int(24 * scale)

        tw_off = max(1, int(1.2 * scale))
        for k, ln in enumerate(lines):
            bbox = draw.textbbox((0, 0), ln, font=font)
            tw = bbox[2] - bbox[0]
            tx = (canvas_w - tw) // 2
            ty = y0 + k * line_h
            if quote_bold:
                draw.text((tx + tw_off, ty + tw_off), ln, fill=(220, 218, 214), font=font)
                draw.text((tx, ty), ln, fill=_TEXT_COLOR, font=font)
            else:
                draw.text((tx, ty), ln, fill=_TEXT_COLOR, font=font)

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
            log.info("ai_motto: templateParams.text set; using fixed motto, no LLM/web image")
            motto, image_prompt = override_text, None
        else:
            motto, image_prompt = _call_llm()

        art = None
        if image_prompt:
            gen_w, gen_h = _infer_fetch_size(w, h)
            art = _fetch_web_motto_image(image_prompt, gen_w, gen_h, motto)

        return _compose(motto, art, w, h)
