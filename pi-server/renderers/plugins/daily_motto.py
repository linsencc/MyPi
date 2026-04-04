from __future__ import annotations

import logging
import os
import subprocess
import uuid
from datetime import date
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from PIL import Image, ImageDraw, ImageFont

from renderers.plugin_base import RenderContext, RenderResult, WallTemplatePlugin

log = logging.getLogger(__name__)

_PLUGIN_DIR = Path(__file__).resolve().parent
_FONT_DIR = _PLUGIN_DIR / "fonts"
_BUNDLED_OTF = _FONT_DIR / "NotoSansSC-Regular.otf"
_NOTO_SUBSET_URL = (
    "https://cdn.jsdelivr.net/gh/notofonts/noto-cjk@Sans2.004/Sans/SubsetOTF/SC/NotoSansSC-Regular.otf"
)

# 无 templateParams.text 时按「本地日期」轮换展示（每日寄语）
_DEFAULT_MOTTOS: tuple[str, ...] = (
    "晨光正好，今天也值得认真过。",
    "慢慢来，把一件小事做好也很好。",
    "心有静气，事缓则圆。",
    "行到水穷处，坐看云起时。",
    "苔花如米小，也学牡丹开。",
    "风物长宜放眼量。",
    "纸上得来终觉浅，绝知此事要躬行。",
    "莫听穿林打叶声，何妨吟啸且徐行。",
    "欲穷千里目，更上一层楼。",
    "山重水复疑无路，柳暗花明又一村。",
    "海内存知己，天涯若比邻。",
    "人生如逆旅，我亦是行人。",
    "竹杖芒鞋轻胜马，谁怕？一蓑烟雨任平生。",
    "沉舟侧畔千帆过，病树前头万木春。",
    "问渠那得清如许？为有源头活水来。",
)

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


def _motto_for_today() -> str:
    i = date.today().toordinal() % len(_DEFAULT_MOTTOS)
    return _DEFAULT_MOTTOS[i]


def _resolve_text(template_params: dict | None) -> str:
    raw = (template_params or {}).get("text")
    if raw is None:
        return _motto_for_today()
    s = str(raw).strip()
    return s if s else _motto_for_today()


def _try_download_noto_subset() -> Path | None:
    if os.environ.get("MYPI_NO_FONT_FETCH", "").strip() in ("1", "true", "yes"):
        return None
    _FONT_DIR.mkdir(parents=True, exist_ok=True)
    part = _BUNDLED_OTF.with_suffix(".part")
    try:
        log.info("daily_motto: downloading CJK font to %s", _BUNDLED_OTF)
        with urlopen(_NOTO_SUBSET_URL, timeout=120) as resp:
            data = resp.read()
        if len(data) < 500_000:
            log.warning("daily_motto: font download too small (%s bytes), ignored", len(data))
            return None
        part.write_bytes(data)
        part.replace(_BUNDLED_OTF)
        return _BUNDLED_OTF
    except (OSError, URLError, TimeoutError, ValueError) as e:
        log.warning("daily_motto: font download failed: %s", e)
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


def _load_cjk_font(size: int) -> ImageFont.FreeTypeFont:
    custom = os.environ.get("MYPI_CJK_FONT", "").strip()
    if custom:
        p = Path(custom)
        if p.is_file():
            font = _open_font(p, size)
            if _font_renders_cjk(font, size):
                return font
        log.warning("daily_motto: MYPI_CJK_FONT not usable: %s", custom)

    if _BUNDLED_OTF.is_file() and _BUNDLED_OTF.stat().st_size > 500_000:
        font = _open_font(_BUNDLED_OTF, size)
        if _font_renders_cjk(font, size):
            return font

    fetched = _try_download_noto_subset()
    if fetched and fetched.is_file():
        font = _open_font(fetched, size)
        if _font_renders_cjk(font, size):
            return font

    for pat in ("Noto Sans CJK SC", "Noto Sans SC", "WenQuanYi Zen Hei", "Source Han Sans SC"):
        fc = _font_from_fontconfig(pat)
        if fc:
            try:
                font = _open_font(fc, size)
                if _font_renders_cjk(font, size):
                    return font
            except OSError:
                continue

    for p in _FONT_CANDIDATES:
        try:
            pp = Path(p)
            if not pp.is_file():
                continue
            font = _open_font(pp, size)
            if _font_renders_cjk(font, size):
                return font
        except OSError:
            continue

    raise RuntimeError(
        "daily_motto: no CJK-capable font found. "
        "Install fonts (e.g. apt install fonts-noto-cjk), place NotoSansSC-Regular.otf under "
        "renderers/plugins/fonts/, or set MYPI_CJK_FONT to a .ttf/.otf path."
    )


def _wrap_lines(text: str, max_chars: int, max_lines: int) -> list[str]:
    t = text.replace("\n", " ").strip()
    if not t:
        return [_motto_for_today()]
    lines: list[str] = []
    i = 0
    while i < len(t) and len(lines) < max_lines:
        lines.append(t[i : i + max_chars])
        i += max_chars
    return lines


class DailyMottoPlugin(WallTemplatePlugin):
    template_id = "daily_motto"
    display_name = "每日寄语"

    def render(self, ctx: RenderContext) -> RenderResult:
        text = _resolve_text(ctx.scene.template_params)
        w, h = 800, 600
        img = Image.new("RGB", (w, h), color=(248, 246, 240))
        draw = ImageDraw.Draw(img)
        size_px = 34
        font = _load_cjk_font(size_px)
        lines = _wrap_lines(text, max_chars=11, max_lines=6)
        line_h = int(size_px * 1.38)
        fill = (35, 38, 42)
        block_h = len(lines) * line_h
        y0 = max(40, (h - block_h) // 2)
        for k, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            tw = bbox[2] - bbox[0]
            x = max(24, (w - tw) // 2)
            draw.text((x, y0 + k * line_h), line[:220], fill=fill, font=font)
        out = Path(ctx.output_dir) / f"daily_motto_{uuid.uuid4().hex}.png"
        img.save(out, format="PNG")
        return RenderResult(image_path=str(out.resolve()))
