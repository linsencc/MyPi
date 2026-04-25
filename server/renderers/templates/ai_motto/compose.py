"""PIL layout: full-bleed art + scrim + quote, or text-only card."""

from __future__ import annotations

import os
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .images import beautify_landscape_art
from renderers.templates.cjk_font import _load_cjk_font
from renderers.templates.cn_date import cn_date_str
from renderers.templates.photo_scrim import fit_image_cover, overlay_bottom_scrim

_MOTTO_REGULAR_CANDIDATES: tuple[tuple[Path, int], ...] = (
    (Path(r"C:\Windows\Fonts\msyh.ttc"), 0),
    (Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"), 0),
    (Path("/usr/share/fonts/truetype/noto/NotoSerifCJK-Regular.ttc"), 0),
    (Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"), 0),
    (Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"), 0),
)

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


def load_motto_quote_font(size: int) -> tuple[ImageFont.FreeTypeFont, bool]:
    """Return (font, has_natural_bold).

    Default prefers **regular** weight (朴素 on scrim). Set ``MYPI_MOTTO_QUOTE_BOLD=1`` to force bold + heavy stroke.
    ``MYPI_MOTTO_FONT`` / ``MYPI_MOTTO_FONT_BOLD`` still override when set.
    """
    force_bold = os.environ.get("MYPI_MOTTO_QUOTE_BOLD", "").strip().lower() in ("1", "true", "yes", "on")

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

    if not force_bold:
        for p, idx in _MOTTO_REGULAR_CANDIDATES:
            f = _try_truetype(p, size, index=idx)
            if f is not None:
                return f, False

    for p, idx in _MOTTO_BOLD_CANDIDATES:
        f = _try_truetype(p, size, index=idx)
        if f is not None:
            return f, True
    return _load_cjk_font(size), False


_BG_COLOR = (250, 248, 243)
_TEXT_COLOR = (30, 32, 36)
_SECONDARY_COLOR = (110, 105, 98)
_SUBTLE_COLOR = (150, 145, 138)
_ACCENT_COLOR = (85, 80, 72)
# Strong contrast (used when MYPI_MOTTO_QUOTE_BOLD=1 or synthetic bold).
_QUOTE_ON_SCRIM_FILL = (244, 240, 228)
_QUOTE_ON_SCRIM_STROKE = (10, 12, 18)
# Plain / 朴素：略亮的字色 + 灰褐细描边，避免粗黑边「海报感」。
_QUOTE_ON_SCRIM_FILL_PLAIN = (252, 250, 245)
_QUOTE_ON_SCRIM_STROKE_PLAIN = (92, 88, 82)
_FOOTER_ON_SCRIM_A = (188, 182, 170)
_FOOTER_ON_SCRIM_B = (138, 132, 122)

# Between closing 「」 and ASCII ` -- ` (display): one ideographic space reads wider than a single ASCII space.
_MOTTO_QUOTE_TO_DASH_GAP = "\u3000"

# Match `」` + flexible space + `--` + space before attribution (LLM uses `」 -- `; display may insert \u3000).
_RE_MOTTO_ATTRIB_SPLIT = re.compile(r"」([\s\u3000]*--\s)")


def _motto_display_widen_quote_dash_gap(motto: str) -> str:
    """Insert a fullwidth space before ` -- ` so quote body and attribution breathe slightly (display only)."""
    if "」" not in motto or "--" not in motto:
        return motto
    m = _RE_MOTTO_ATTRIB_SPLIT.search(motto)
    if not m:
        return motto
    inner = m.group(1)
    if _MOTTO_QUOTE_TO_DASH_GAP in inner:
        return motto
    return motto[: m.start() + 1] + _MOTTO_QUOTE_TO_DASH_GAP + inner + motto[m.end() :]


def _draw_motto_footer(
    draw: ImageDraw.ImageDraw,
    canvas_w: int,
    footer_y: int,
    scale: float,
    *,
    on_scrim: bool,
) -> None:
    small = _load_cjk_font(max(10, int(12 * scale)))
    date_str = cn_date_str()
    attr_str = "— 每日寄语"
    spacer = int(20 * scale)
    db = draw.textbbox((0, 0), date_str, font=small)
    ab = draw.textbbox((0, 0), attr_str, font=small)
    dw, aw = db[2] - db[0], ab[2] - ab[0]
    total = dw + spacer + aw
    x0 = (canvas_w - total) // 2
    if on_scrim:
        draw.text((x0, footer_y), date_str, fill=_FOOTER_ON_SCRIM_A, font=small)
        draw.text((x0 + dw + spacer, footer_y), attr_str, fill=_FOOTER_ON_SCRIM_B, font=small)
    else:
        draw.text((x0, footer_y), date_str, fill=_SECONDARY_COLOR, font=small)
        draw.text((x0 + dw + spacer, footer_y), attr_str, fill=_SUBTLE_COLOR, font=small)


# Prefer breaking after these (CJK / ASCII punctuation); avoid ugly mid-word cuts where possible.
# 不含 ASCII '-'，避免把 motto 里的「 -- 」拆断到两行。
# 不含「」：否则易在直角引号处断行，导致 closing 「 单独成行。
_MOTTO_BREAK_AFTER = frozenset("，、；。：！？．!?,)）】』〉》…—　 \t")


def _wrap_segment_greedy(segment: str, max_chars: int, max_lines: int) -> list[str]:
    """Pack segment into lines up to max_lines; prefer breaks after punctuation within max_chars."""
    s = segment.replace("\n", " ").strip()
    if not s:
        return []
    if max_chars < 4:
        max_chars = 4
    lines: list[str] = []
    pos = 0
    while pos < len(s) and len(lines) < max_lines:
        remain = len(s) - pos
        if remain <= max_chars:
            lines.append(s[pos:])
            pos = len(s)
            break
        hi = pos + max_chars
        min_j = pos + max(4, max_chars * 55 // 100)
        best = hi
        for j in range(hi, min_j - 1, -1):
            if j <= pos:
                break
            if s[j - 1] in _MOTTO_BREAK_AFTER:
                # 勿在句末标点（。！？）与紧随的 \u300d 之间断行，避免 closing bracket alone on next line.
                if j < len(s) and s[j] == "」" and s[j - 1] in "。！？":
                    continue
                best = j
                break
        lines.append(s[pos:best])
        pos = best
    if pos < len(s) and lines:
        lines[-1] = lines[-1] + s[pos:]
    return lines


def _wrap_motto_lines(text: str, max_chars: int, max_lines: int) -> list[str]:
    """Motto-aware wrap: keep `」 … -- 出处` on its own last line when it fits; prefer CJK punctuation breaks."""
    t = text.replace("\n", " ").strip()
    if not t:
        return ["晨光正好，今天也值得认真过。"]

    m = _RE_MOTTO_ATTRIB_SPLIT.search(t)
    if not m:
        return _wrap_segment_greedy(t, max_chars, max_lines)

    idx = m.start()
    head = t[: idx + len("」")]
    suffix = t[idx + len("」") :]
    if not suffix:
        return _wrap_segment_greedy(head, max_chars, max_lines)

    if len(suffix) <= max_chars:
        body_cap = max(1, max_lines - 1)
        body_lines = _wrap_segment_greedy(head, max_chars, body_cap)
        return body_lines + [suffix]

    body_cap = max(1, (max_lines + 1) // 2)
    body_lines = _wrap_segment_greedy(head, max_chars, body_cap)
    rest = max(1, max_lines - len(body_lines))
    suf_lines = _wrap_segment_greedy(suffix, max_chars, rest)
    return body_lines + suf_lines[:rest]


def _split_attribution_to_own_line(lines: list[str]) -> list[str]:
    """If `」 … -- 出处` was wrapped onto one line, force ` … -- …` onto its own line(s)."""
    out: list[str] = []
    for ln in lines:
        mo = _RE_MOTTO_ATTRIB_SPLIT.search(ln)
        if not mo:
            out.append(ln)
            continue
        j = mo.start()
        before = ln[: j + len("」")].strip()
        after = ln[j + len("」") :]
        if before:
            out.append(before)
        if after.strip():
            out.append(after)
    return out


def _fix_lonely_closing_corner(lines: list[str]) -> list[str]:
    """Merge a line that is only the closing 「」 onto the previous line (layout safety net)."""
    out: list[str] = []
    i = 0
    while i < len(lines):
        if i + 1 < len(lines) and lines[i + 1].strip() == "」":
            out.append(lines[i].rstrip() + "」")
            i += 2
            continue
        out.append(lines[i])
        i += 1
    return out


def _motto_wrap_pipeline(motto: str, max_chars: int, max_lines: int) -> list[str]:
    motto = _motto_display_widen_quote_dash_gap(motto)
    return _fix_lonely_closing_corner(
        _split_attribution_to_own_line(_wrap_motto_lines(motto, max_chars=max_chars, max_lines=max_lines))
    )


def _first_attribution_line_index(lines: list[str]) -> int | None:
    """Index of first line that is the `-- 出处` row (after split), for extra vertical gap above it."""
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith("--"):
            return i
    return None


def compose_motto(
    motto: str,
    art: Image.Image | None,
    canvas_w: int,
    canvas_h: int,
) -> Image.Image:
    img = Image.new("RGB", (canvas_w, canvas_h), color=_BG_COLOR)
    draw = ImageDraw.Draw(img)
    scale = min(canvas_w, canvas_h) / 600
    cx = canvas_w // 2
    margin = max(28, int(canvas_w * 0.058))

    if art:
        fitted = fit_image_cover(art, canvas_w, canvas_h)
        fitted = beautify_landscape_art(fitted)
        img.paste(fitted, (0, 0))

        scrim_start = int(canvas_h * 0.36)
        overlay_bottom_scrim(img, scrim_start, canvas_h - scrim_start)
        draw = ImageDraw.Draw(img)

        text_zone_center = int(canvas_h * 0.702)
        size_px = max(21, int(30 * scale))
        font, quote_bold = load_motto_quote_font(size_px)
        raw_max = max(8, int((canvas_w - margin * 2) / (size_px * 1.02)))
        n = len(motto)
        if n <= raw_max:
            max_chars = n
        elif n <= raw_max * 2:
            max_chars = (n + 1) // 2
        else:
            max_chars = raw_max
        lines = _motto_wrap_pipeline(motto, max_chars=max_chars, max_lines=6)
        ink_heights: list[int] = []
        for ln in lines:
            bb = draw.textbbox((0, 0), ln, font=font)
            ink_heights.append(bb[3] - bb[1])
        line_gap = int(size_px * (0.28 if not quote_bold else 0.2))
        line_step = max(ink_heights) + max(6, line_gap)
        attrib_idx = _first_attribution_line_index(lines)
        attrib_air = int(size_px * (0.62 if not quote_bold else 0.45))
        _air = attrib_air if attrib_idx is not None else 0
        block_h = (len(lines) - 1) * line_step + max(ink_heights) + _air - max(0, int(size_px * 0.05))
        y0 = text_zone_center - block_h // 2
        footer_reserve = canvas_h - max(18, int(24 * scale)) - int(14 * scale)
        last_bottom = (
            y0
            + (len(lines) - 1) * line_step
            + (attrib_air if attrib_idx is not None and (len(lines) - 1) >= attrib_idx else 0)
            + max(ink_heights)
        )
        if last_bottom > footer_reserve:
            y0 = max(int(canvas_h * 0.12), footer_reserve - last_bottom + y0)

        if quote_bold:
            q_fill, q_stroke = _QUOTE_ON_SCRIM_FILL, _QUOTE_ON_SCRIM_STROKE
            stroke_w = max(1, int(1.55 * scale))
        else:
            q_fill, q_stroke = _QUOTE_ON_SCRIM_FILL_PLAIN, _QUOTE_ON_SCRIM_STROKE_PLAIN
            # 细描边：比旧版粗黑边淡得多，但仍利于 e-ink / 复杂底图辨认。
            stroke_w = max(1, int(0.42 * scale))
        for k, ln in enumerate(lines):
            bbox = draw.textbbox((0, 0), ln, font=font)
            tw = bbox[2] - bbox[0]
            tx = (canvas_w - tw) // 2
            y_shift = attrib_air if attrib_idx is not None and k >= attrib_idx else 0
            ty = y0 + k * line_step + y_shift - bbox[1]
            draw.text(
                (tx, ty),
                ln,
                fill=q_fill,
                font=font,
                stroke_width=stroke_w,
                stroke_fill=q_stroke,
            )

        footer_y = canvas_h - max(18, int(24 * scale))
        _draw_motto_footer(draw, canvas_w, footer_y, scale, on_scrim=True)

    else:
        bar_w = int(32 * scale)
        bar_h = max(1, int(2 * scale))
        bar_y = int(canvas_h * 0.30)
        draw.rectangle(
            [(cx - bar_w // 2, bar_y), (cx + bar_w // 2, bar_y + bar_h)],
            fill=_ACCENT_COLOR,
        )

        size_px = max(26, int(36 * scale))
        font, quote_bold = load_motto_quote_font(size_px)
        max_chars = max(6, int((canvas_w - margin * 2) / (size_px * 1.02)))
        lines = _motto_wrap_pipeline(motto, max_chars=max_chars, max_lines=6)
        ink_heights: list[int] = []
        for ln in lines:
            bb = draw.textbbox((0, 0), ln, font=font)
            ink_heights.append(bb[3] - bb[1])
        line_gap2 = int(size_px * (0.26 if not quote_bold else 0.22))
        line_step = max(ink_heights) + max(6, line_gap2)
        attrib_idx2 = _first_attribution_line_index(lines)
        attrib_air2 = int(size_px * (0.52 if not quote_bold else 0.38))
        _air2 = attrib_air2 if attrib_idx2 is not None else 0
        block_h = (len(lines) - 1) * line_step + max(ink_heights) + _air2 - max(0, int(size_px * 0.06))
        y0 = bar_y + bar_h + int(22 * scale)

        tw_off = max(1, int(1.0 * scale))
        text_fill = _TEXT_COLOR if quote_bold else (42, 44, 48)
        for k, ln in enumerate(lines):
            bbox = draw.textbbox((0, 0), ln, font=font)
            tw = bbox[2] - bbox[0]
            tx = (canvas_w - tw) // 2
            y_shift = attrib_air2 if attrib_idx2 is not None and k >= attrib_idx2 else 0
            ty = y0 + k * line_step + y_shift - bbox[1]
            if quote_bold:
                draw.text((tx + tw_off, ty + tw_off), ln, fill=(228, 226, 222), font=font)
                draw.text((tx, ty), ln, fill=text_fill, font=font)
            else:
                draw.text((tx, ty), ln, fill=text_fill, font=font)

        footer_y = y0 + len(lines) * line_step + max(10, int(16 * scale))
        _draw_motto_footer(draw, canvas_w, footer_y, scale, on_scrim=False)

    return img
