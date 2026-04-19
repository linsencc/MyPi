"""AI-generated daily message template with a Pinterest-sourced illustration.

Targets **full-color RGB** for color e-ink. Downloaded photos are rejected if they look **black &
white**; if no color image is found after retries, the layout falls back to **text only** (no art).

Each render:
  1. Calls LLM to generate a Chinese motto + English image prompt (landscape / scenery, any style)
  2. Fetches a full-color landscape image from Pinterest (or fallbacks; see below)
  3. Composes a full-bleed image with text overlay (portrait-friendly, image is cropped to the frame)

Environment variables:
  MYPI_LLM_API_KEY             – OpenAI-compatible API key (e.g. OpenRouter)
  MYPI_LLM_BASE_URL            – API base URL (default: https://openrouter.ai/api/v1)
  MYPI_LLM_MODEL               – Model id (default: deepseek/deepseek-chat on OpenRouter)
  MYPI_LLM_TIMEOUT             – LLM timeout seconds (default: 20)
  MYPI_LLM_PROXY               – HTTP(S) proxy for LLM calls
  MYPI_PINTEREST_ACCESS_TOKEN  – Pinterest API OAuth access token (or PINTEREST_ACCESS_TOKEN)
  MYPI_PINTEREST_COUNTRY       – ISO 3166-1 alpha-2 for partner search (default: US)
  MYPI_PINTEREST_BOARD_ID      – Optional numeric board id (e.g. wallpaper moodboard like pinterest.com/elliotprl/wallpaper/).
                                  When set, pins from this board load first (same Pinterest account as token), then partner search.
                                  Resolve id via Pinterest API or saved pin JSON — not the URL slug alone.
  MYPI_MOTTO_FETCH_MAX_SIDE    – Max long edge when downloading (default: 2400; matches frame aspect)
  MYPI_MOTTO_COLOR_BOOST       – PIL Color enhance on the photo layer (default: 1.15 for color e-ink). Set 1.0 to disable.
  MYPI_MOTTO_BEAUTIFY          – if 0: skip mild contrast/sat on downloaded art (default: 1 / on).
  MYPI_MOTTO_SCRIM_MAX         – bottom dark scrim max opacity 0–1 (default: 0.76). Stronger = darker footer band for text.
  MYPI_MOTTO_FONT              – Optional path to .ttf/.otf/.ttc for the quote (literary title font).
  MYPI_MOTTO_FONT_BOLD         – Optional path to a bolder face for the quote; if unset, stroke is used on MYPI_MOTTO_FONT or default CJK.
  MYPI_MOTTO_IMAGE_NO_PROXY      – if 1/true: Pinterest/image HTTP without proxy (LLM may still use proxy)
  MYPI_MOTTO_OFFLINE_IMAGE       – Optional path to a JPEG/PNG used when remote image fetch fails (after image_prompt).
"""
from __future__ import annotations

import hashlib
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

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps, ImageStat

from renderers.template_base import RenderContext, WallTemplate
from renderers.templates.cjk_font import _load_cjk_font, _wrap_lines
from renderers.templates.cn_date import cn_date_str
from renderers.templates.photo_scrim import (
    download_image_url,
    fit_image_cover,
    infer_fetch_size,
    overlay_bottom_scrim,
    to_full_color_rgb,
)
from renderers.templates.motto_diversity import (
    RETRY_DIVERSIFY_SUFFIX,
    append_motto_to_recent,
    format_recent_block,
    is_motto_too_similar,
    load_recent_mottos,
    pick_motto_stratum,
)

log = logging.getLogger(__name__)

# ── LLM config ──────────────────────────────────────────────────────
# Defaults target OpenRouter (OpenAI-compatible). Base URL and model id must match the key provider.
_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
_DEFAULT_MODEL = "deepseek/deepseek-chat"
_DEFAULT_TIMEOUT = 20

_SYSTEM_PROMPT = textwrap.dedent("""\
    你是一位每天陪伴用户的智慧伙伴。请生成以下两项内容，以纯 JSON 返回：

    {
      "motto": "「正文摘录」 -- 出处",
      "image_prompt": "English keywords for landscape wallpaper image search"
    }

    严格要求：
    - 只输出上述 JSON，不加任何其他内容、标签或解释
    - motto（核心）**格式固定**（须一字不差遵循标点与空格）：
      · 整段必须为：`「……」 -- 出处`
      · 正文用**中文直角引号**「」包裹；`--` 为**两个英文连字符**，其**左右各一个半角空格**
      · **出处**：文学写书名或作者（如 `红楼梦` 或 `曹雪芹`）；影视写 `《片名》`；诗词古文写作者；人物写人名（可带朝代/国别简称）
      · 避免空洞鸡汤（少用「愿你」「加油」「不负韶华」等）；翻译句读感要像中文书面语
    - **用户消息**中会给出【本次唯一维度】与【近期去重】。你必须**同时**遵守：
      · 选题**只能**落在该维度内（例如指定「仅华语影视」时，不得输出欧美片；指定「仅诗词」时不得输出影视）。
      · 寄语须**明显区别于**「近期去重」列表，勿逐字复述或仅改一两字。
      · 勿依赖模型训练数据里最常出现的少数「全球通用品」；宁可选略冷门但贴切的作品。
      · **文风简约**：正文宜短、洗练，避免堆砌修辞与长从句，像书签摘句而非散文段。
      整段 motto（含「」、`--` 与出处）**34 字以内**，不打招呼、不写日期。
    - image_prompt: 英文关键词串，用于找**全彩桌面风景壁纸插画**（竖屏满幅背景 + 底部叠字），与寄语意境相合。
      审美对齐 Pinterest 上 **desktop wallpaper art / anime scenery wallpaper** 类画板（如偏插画、水彩、日系动画背景感、治愈系远景）：
      * **优先**：手绘/数字**插画绘景**、**watercolor**、**anime landscape illustration**、**aesthetic desktop background**、
        whimsical、painterly、**cozy village**、**mountain lake**、coastal town、flower field、rooftop view、balcony scenery、
        tree-lined street、**ghibli-inspired** 或 **studio ghibli style** 式开阔自然（**无人物或人物极小不可辨**，勿主体人像）
      * **次要**才可偏写实风光片，且须柔和、梦幻、壁纸感，禁止新闻/街拍/室内家居为主
      * 必须 **full color**、**colorful**、soft light；禁止黑白、sepia、人脸特写、文字水印
      * 适合 **vertical / portrait** 或易竖裁的横幅远景；不要画面内文字、画框
      * 控制在 40–60 词，多写画风词（illustration / wallpaper / anime scenery / aesthetic）
""")

_USER_PROMPT = (
    "请给我今天一句**简短洗练**的寄语（motto 严格为 `「正文」 -- 出处`，正文尽量短），"
    "以及相配的英文 image_prompt：便于检索 **desktop wallpaper art / anime scenery wallpaper** 类插画远景。"
)

# ── Fallbacks ───────────────────────────────────────────────────────
_FALLBACK_MESSAGES = (
    "「人生如逆旅，我亦是行人。」 -- 苏轼",
    "「世上只有一种英雄主义，就是在认清生活真相之后依然热爱生活。」 -- 罗曼·罗兰",
    "「一个人知道自己为什么而活，就可以忍受任何一种生活。」 -- 尼采",
    "「我来到这个世界上，为了看看太阳和蓝色的地平线。」 -- 巴尔蒙特",
    "「路漫漫其修远兮，吾将上下而求索。」 -- 屈原",
    "「生活不可能像你想象得那么好，但也不会像你想象得那么糟。」 -- 莫泊桑",
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


def _assistant_content_from_completion(body: object) -> str:
    """OpenAI-style chat completion message content (string or multimodal list)."""
    if not isinstance(body, dict):
        return ""
    try:
        choices = body["choices"]
        msg = choices[0]["message"]
    except (KeyError, IndexError, TypeError):
        return ""
    if not isinstance(msg, dict):
        return ""
    c = msg.get("content")
    if isinstance(c, str):
        return c.strip()
    if isinstance(c, list):
        parts: list[str] = []
        for item in c:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    t = item.get("text")
                    if isinstance(t, str):
                        parts.append(t)
                elif isinstance(item.get("text"), str):
                    parts.append(str(item["text"]))
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts).strip()
    return ""


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

    recent = load_recent_mottos()
    stratum = pick_motto_stratum()
    log.info("ai_motto: stratum=%s recent_lines=%s", stratum.key, len(recent))
    base_user = (
        f"{_USER_PROMPT}\n\n{stratum.instruction}\n\n{format_recent_block(recent)}"
    )
    opener = _build_opener()

    motto = ""
    image_prompt: str | None = None
    raw = ""

    for attempt in range(3):
        user_content = base_user if attempt == 0 else f"{base_user}\n\n{RETRY_DIVERSIFY_SUFFIX}"
        payload = json.dumps({
            "model": model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": 400,
            "temperature": 0.92,
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

        try:
            with opener.open(req, timeout=timeout) as resp:
                body = json.loads(resp.read())
            raw = _assistant_content_from_completion(body)
            if not raw:
                log.warning(
                    "ai_motto: LLM empty assistant content (attempt %s)",
                    attempt + 1,
                )
                if attempt < 2:
                    continue
                return _get_fallback(), None
            log.info("ai_motto: LLM attempt %s raw %d chars", attempt + 1, len(raw))

            data = _parse_llm_json_blob(raw)
            if not data:
                log.warning(
                    "ai_motto: LLM response is not valid JSON (attempt %s)",
                    attempt + 1,
                )
                if attempt < 2:
                    continue
                text = _strip_thinking(raw)
                return text or _get_fallback(), None

            motto = (data.get("motto") or "").strip()
            image_prompt = _image_prompt_from_data(data)
            if not motto:
                motto = _strip_thinking(raw) or _get_fallback()
            if motto and not image_prompt:
                log.info("ai_motto: LLM returned motto but empty image_prompt; text-only layout")

            if motto and not is_motto_too_similar(motto, recent):
                append_motto_to_recent(motto)
                return motto, image_prompt

            if attempt < 2:
                log.warning(
                    "ai_motto: motto too similar to recent or weak diversity, retrying (%s/2)",
                    attempt + 1,
                )
                continue
            log.warning("ai_motto: still similar after retries; using last motto")
            append_motto_to_recent(motto)
            return motto, image_prompt
        except urllib.error.HTTPError as exc:
            err_body = ""
            try:
                err_body = exc.read().decode("utf-8", errors="replace")[:600]
            except Exception:
                pass
            log.warning(
                "ai_motto: LLM HTTP %s body_prefix=%r",
                exc.code,
                err_body[:400],
            )
            if attempt < 2 and exc.code in (408, 425, 429, 500, 502, 503, 504):
                time.sleep(0.8 * (attempt + 1))
                continue
            return _get_fallback(), None
        except json.JSONDecodeError as exc:
            log.warning("ai_motto: LLM response not JSON (attempt %s): %s", attempt + 1, exc)
            if attempt < 2:
                continue
            return _get_fallback(), None
        except Exception as exc:
            log.warning("ai_motto: LLM call failed (attempt %s): %s", attempt + 1, exc)
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
                continue
            return _get_fallback(), None

    return motto or _get_fallback(), image_prompt


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
    "composition", "cinematic", "photography", "photo", "realistic",
    "impressionist", "pastel", "film", "grain", "bokeh",
    "studio", "wash", "sumi", "monochrome", "sepia",
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
        if len(picked) >= 6:
            break
    if not picked:
        return "anime,landscape,scenic,wallpaper,watercolor"
    return ",".join(picked)


def _pinterest_search_query_from_tags(tags_csv: str) -> str:
    """Partner search: align with desktop wallpaper / anime scenery mood boards (e.g. wallpaper art collections)."""
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


def _beautify_landscape_art(img: Image.Image) -> Image.Image:
    """Mild contrast + saturation so wallpapers read richer on e-ink (cheap on Pi)."""
    v = os.environ.get("MYPI_MOTTO_BEAUTIFY", "1").strip().lower()
    if v in ("0", "false", "no", "off"):
        return img
    rgb = img.convert("RGB")
    rgb = ImageEnhance.Contrast(rgb).enhance(1.06)
    rgb = ImageEnhance.Color(rgb).enhance(1.05)
    return rgb


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
        img = download_image_url(url, opener, log_prefix="ai_motto")
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
        img = download_image_url(lf_url, opener, log_prefix="ai_motto")
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
        img = download_image_url(url, opener, log_prefix="ai_motto")
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


def _offline_motto_art(gen_w: int, gen_h: int) -> Image.Image:
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


# ── Composition ─────────────────────────────────────────────────────

_BG_COLOR = (250, 248, 243)
_TEXT_COLOR = (30, 32, 36)
_SECONDARY_COLOR = (110, 105, 98)
_SUBTLE_COLOR = (150, 145, 138)
_ACCENT_COLOR = (85, 80, 72)
# Full-bleed: **dark bottom scrim** (not pale wash) so light text + dark stroke stay readable.
_SCRIM_RGB = (22, 26, 36)
_QUOTE_ON_SCRIM_FILL = (244, 240, 228)
_QUOTE_ON_SCRIM_STROKE = (10, 12, 18)
_FOOTER_ON_SCRIM_A = (188, 182, 170)
_FOOTER_ON_SCRIM_B = (138, 132, 122)


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
        fitted = fit_image_cover(art, canvas_w, canvas_h)
        fitted = _beautify_landscape_art(fitted)
        img.paste(fitted, (0, 0))

        scrim_start = int(canvas_h * 0.38)
        overlay_bottom_scrim(img, scrim_start, canvas_h - scrim_start)
        draw = ImageDraw.Draw(img)

        # Text sits in the lower third over the scrim (light fill + dark stroke)
        text_zone_center = int(canvas_h * 0.74)
        size_px = max(22, int(31 * scale))
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
        line_h = int(size_px * 1.44)
        block_h = len(lines) * line_h
        y0 = text_zone_center - block_h // 2

        stroke_w = max(1, int(1.75 * scale)) if not quote_bold else max(1, int(1.55 * scale))
        for k, ln in enumerate(lines):
            bbox = draw.textbbox((0, 0), ln, font=font)
            tw = bbox[2] - bbox[0]
            tx = (canvas_w - tw) // 2
            ty = y0 + k * line_h
            draw.text(
                (tx, ty),
                ln,
                fill=_QUOTE_ON_SCRIM_FILL,
                font=font,
                stroke_width=stroke_w,
                stroke_fill=_QUOTE_ON_SCRIM_STROKE,
            )

        # Footer: date + attribution
        footer_y = canvas_h - int(26 * scale)
        small = _load_cjk_font(max(10, int(12 * scale)))
        date_str = cn_date_str()
        attr_str = "— 每日寄语"
        spacer = int(20 * scale)
        db = draw.textbbox((0, 0), date_str, font=small)
        ab = draw.textbbox((0, 0), attr_str, font=small)
        dw, aw = db[2] - db[0], ab[2] - ab[0]
        total = dw + spacer + aw
        x0 = (canvas_w - total) // 2
        draw.text((x0, footer_y), date_str, fill=_FOOTER_ON_SCRIM_A, font=small)
        draw.text((x0 + dw + spacer, footer_y), attr_str, fill=_FOOTER_ON_SCRIM_B, font=small)

    else:
        # ── Text only (no image) ─────────────────────────────
        bar_w = int(32 * scale)
        bar_h = max(1, int(2 * scale))
        bar_y = int(canvas_h * 0.32)
        draw.rectangle(
            [(cx - bar_w // 2, bar_y), (cx + bar_w // 2, bar_y + bar_h)],
            fill=_ACCENT_COLOR,
        )

        size_px = max(26, int(35 * scale))
        font, quote_bold = _load_motto_quote_font(size_px)
        max_chars = max(6, int((canvas_w - margin * 2) / (size_px * 1.05)))
        lines = _wrap_lines(motto, max_chars=max_chars, max_lines=4)
        line_h = int(size_px * 1.48)
        block_h = len(lines) * line_h
        y0 = bar_y + bar_h + int(20 * scale)

        tw_off = max(1, int(1.0 * scale))
        for k, ln in enumerate(lines):
            bbox = draw.textbbox((0, 0), ln, font=font)
            tw = bbox[2] - bbox[0]
            tx = (canvas_w - tw) // 2
            ty = y0 + k * line_h
            if quote_bold:
                draw.text((tx + tw_off, ty + tw_off), ln, fill=(228, 226, 222), font=font)
                draw.text((tx, ty), ln, fill=_TEXT_COLOR, font=font)
            else:
                draw.text((tx, ty), ln, fill=_TEXT_COLOR, font=font)

        text_bottom = y0 + block_h
        footer_y = text_bottom + int(20 * scale)
        small = _load_cjk_font(max(10, int(12 * scale)))
        date_str = cn_date_str()
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
        gen_w, gen_h = infer_fetch_size(w, h)
        if image_prompt:
            art = _fetch_web_motto_image(image_prompt, gen_w, gen_h, motto)
            if art is None:
                log.info("ai_motto: remote image unavailable; using offline wallpaper")
                art = _offline_motto_art(gen_w, gen_h)
        elif not override_text:
            # No image_prompt (e.g. LLM key unset): still full-bleed background so the card is not plain text-only.
            art = _offline_motto_art(gen_w, gen_h)

        return _compose(motto, art, w, h)
