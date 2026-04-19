"""Shared CJK font resolution and simple line wrapping for text-based templates."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from PIL import ImageFont

log = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parent
_FONT_DIR = _TEMPLATE_DIR / "fonts"
_BUNDLED_OTF = _FONT_DIR / "NotoSansSC-Regular.otf"
_NOTO_SUBSET_URL = (
    "https://cdn.jsdelivr.net/gh/notofonts/noto-cjk@Sans2.004/Sans/SubsetOTF/SC/NotoSansSC-Regular.otf"
)

_WRAP_FALLBACK_LINE = "晨光正好，今天也值得认真过。"

_FONT_CANDIDATES: tuple[str | Path, ...] = (
    Path(r"C:\Windows\Fonts\msyh.ttc"),
    Path(r"C:\Windows\Fonts\msyhbd.ttc"),
    Path(r"C:\Windows\Fonts\simhei.ttf"),
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.otf"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
    Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
    Path("/usr/share/fonts/truetype/arphic/uming.ttc"),
    Path("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"),
)


def _try_download_noto_subset() -> Path | None:
    if os.environ.get("MYPI_NO_FONT_FETCH", "").strip() in ("1", "true", "yes"):
        return None
    _FONT_DIR.mkdir(parents=True, exist_ok=True)
    part = _BUNDLED_OTF.with_suffix(".part")
    try:
        log.info("cjk_font: downloading CJK font to %s", _BUNDLED_OTF)
        with urlopen(_NOTO_SUBSET_URL, timeout=120) as resp:
            data = resp.read()
        if len(data) < 500_000:
            log.warning("cjk_font: font download too small (%s bytes), ignored", len(data))
            return None
        part.write_bytes(data)
        part.replace(_BUNDLED_OTF)
        return _BUNDLED_OTF
    except (OSError, URLError, TimeoutError, ValueError) as e:
        log.warning("cjk_font: font download failed: %s", e)
        try:
            if part.is_file():
                part.unlink(missing_ok=True)
        except OSError:
            pass
        return None


def _font_from_fontconfig(pattern: str) -> Path | None:
    try:
        out = subprocess.check_output(
            ["fc-match", "-f", "%{file}\n", pattern],
            text=True,
            timeout=3,
            stderr=subprocess.DEVNULL,
        )
        p = Path(out.strip())
        if p.is_file():
            return p
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass
    return None


def _open_font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    suf = path.suffix.lower()
    if suf == ".ttc":
        return ImageFont.truetype(str(path), size=size, index=0)
    return ImageFont.truetype(str(path), size=size)


def _font_renders_cjk(font: ImageFont.ImageFont, size: int) -> bool:
    try:
        probe = "寄语中"
        if hasattr(font, "getbbox"):
            x0, y0, x1, y1 = font.getbbox(probe)
            return (x1 - x0) > 1 and (y1 - y0) > 1
        m = font.getmask(probe)
        return m.size[0] > 2 and m.size[1] > 2
    except (OSError, TypeError, ValueError, AttributeError):
        return False


_cached_font_path: Path | None = None


def _resolve_cjk_font_path(allow_download: bool = False) -> Path:
    global _cached_font_path
    if _cached_font_path is not None:
        return _cached_font_path

    probe_size = 20

    custom = os.environ.get("MYPI_CJK_FONT", "").strip()
    if custom:
        p = Path(custom)
        if p.is_file():
            font = _open_font(p, probe_size)
            if _font_renders_cjk(font, probe_size):
                _cached_font_path = p
                return p
        log.warning("cjk_font: MYPI_CJK_FONT not usable: %s", custom)

    if _BUNDLED_OTF.is_file() and _BUNDLED_OTF.stat().st_size > 500_000:
        font = _open_font(_BUNDLED_OTF, probe_size)
        if _font_renders_cjk(font, probe_size):
            _cached_font_path = _BUNDLED_OTF
            return _BUNDLED_OTF

    if allow_download:
        fetched = _try_download_noto_subset()
        if fetched and fetched.is_file():
            font = _open_font(fetched, probe_size)
            if _font_renders_cjk(font, probe_size):
                _cached_font_path = fetched
                return fetched

    for pat in ("Noto Sans CJK SC", "Noto Sans SC", "WenQuanYi Zen Hei", "Source Han Sans SC"):
        fc = _font_from_fontconfig(pat)
        if fc:
            try:
                font = _open_font(fc, probe_size)
                if _font_renders_cjk(font, probe_size):
                    _cached_font_path = fc
                    return fc
            except OSError:
                continue

    for p in _FONT_CANDIDATES:
        try:
            pp = Path(p)
            if not pp.is_file():
                continue
            font = _open_font(pp, probe_size)
            if _font_renders_cjk(font, probe_size):
                _cached_font_path = pp
                return pp
        except OSError:
            continue

    raise RuntimeError(
        "cjk_font: no CJK-capable font found. "
        "Install fonts (e.g. apt install fonts-noto-cjk), place NotoSansSC-Regular.otf under "
        "renderers/templates/fonts/, or set MYPI_CJK_FONT to a .ttf/.otf path."
    )


def preflight_font() -> None:
    """Call at startup to eagerly resolve (and optionally download) the font."""
    _resolve_cjk_font_path(allow_download=True)
    log.info("cjk_font: font resolved → %s", _cached_font_path)


def _load_cjk_font(size: int) -> ImageFont.FreeTypeFont:
    p = _resolve_cjk_font_path(allow_download=False)
    return _open_font(p, size)


def _wrap_lines(text: str, max_chars: int, max_lines: int) -> list[str]:
    t = text.replace("\n", " ").strip()
    if not t:
        return [_WRAP_FALLBACK_LINE]
    lines: list[str] = []
    i = 0
    while i < len(t) and len(lines) < max_lines:
        lines.append(t[i : i + max_chars])
        i += max_chars
    return lines
