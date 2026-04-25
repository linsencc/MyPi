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
# Plain / 朴素：略偏乳白（略压最亮点）+ 较深暖灰描边，兼顾亮云底上的分离度。
_QUOTE_ON_SCRIM_FILL_PLAIN = (250, 248, 242)
_QUOTE_ON_SCRIM_STROKE_PLAIN = (56, 52, 48)
_FOOTER_ON_SCRIM_A = (188, 182, 174)
_FOOTER_ON_SCRIM_B = (136, 130, 122)

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
    attr_suffix: str = "— 每日寄语",
) -> None:
    small = _load_cjk_font(max(10, int(12 * scale)))
    date_str = cn_date_str()
    attr_str = attr_suffix
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


def _is_attribution_line(ln: str) -> bool:
    return ln.lstrip().startswith("--")


# 出处行相对正文字号（略小一档）。
_MOTTO_ATTRIB_SIZE_RATIO = 0.86


def _quote_font_for_line(ln: str, font: ImageFont.ImageFont, font_attrib: ImageFont.ImageFont) -> ImageFont.ImageFont:
    return font_attrib if _is_attribution_line(ln) else font


def _ink_heights_for_motto_lines(
    lines: list[str],
    font: ImageFont.ImageFont,
    font_attrib: ImageFont.ImageFont,
    draw: ImageDraw.ImageDraw,
) -> list[int]:
    out: list[int] = []
    for ln in lines:
        f = _quote_font_for_line(ln, font, font_attrib)
        bb = draw.textbbox((0, 0), ln, font=f)
        out.append(bb[3] - bb[1])
    return out


def flatten_lines_spec_for_motto_scrim(
    lines_spec: list[str | None],
) -> tuple[list[str], frozenset[int]]:
    """Turn ``[a, b, None, c]`` into lines ``[a,b,c]`` + break indices ``{2}`` (extra gap before line 2)."""
    lines: list[str] = []
    breaks: set[int] = set()
    for item in lines_spec:
        if item is None:
            breaks.add(len(lines))
            continue
        t = str(item).strip()
        if not t:
            continue
        lines.append(t[:500])
    return lines, frozenset(breaks)


def _motto_on_scrim_para_extra(
    k: int, breaks_before_line: set[int] | frozenset[int], para_unit: int
) -> int:
    return para_unit * sum(1 for b in breaks_before_line if b <= k)


def layout_motto_on_scrim_body(
    draw: ImageDraw.ImageDraw,
    canvas_w: int,
    canvas_h: int,
    lines: list[str],
    breaks_before_line: set[int] | frozenset[int],
    size_px: int,
) -> dict:
    """Compute 每日寄语配图分支同款竖排与描边参数；``lines`` 为已定宽的物理行。"""
    scale = min(canvas_w, canvas_h) / 600
    # 与 compose_motto 配图分支一致：靠下，落在 scrim 压暗更实的一段。
    text_zone_center = int(canvas_h * 0.718)
    footer_pad = max(20, int(26 * scale))
    footer_reserve = canvas_h - footer_pad - int(18 * scale)

    if not lines:
        return {
            "y0": text_zone_center,
            "line_step": 0,
            "font": None,
            "font_attrib": None,
            "quote_bold": False,
            "size_px": size_px,
            "size_attrib": max(14, int(size_px * _MOTTO_ATTRIB_SIZE_RATIO)),
            "stroke_w": 1,
            "q_fill": _QUOTE_ON_SCRIM_FILL_PLAIN,
            "q_stroke": _QUOTE_ON_SCRIM_STROKE_PLAIN,
            "attrib_idx": None,
            "attrib_air": 0,
            "breaks_before_line": frozenset(breaks_before_line),
            "last_bottom": text_zone_center,
            "footer_pad": footer_pad,
        }

    font, quote_bold = load_motto_quote_font(size_px)
    size_attrib = max(14, int(size_px * _MOTTO_ATTRIB_SIZE_RATIO))
    font_attrib, _ = load_motto_quote_font(size_attrib)
    ink_heights = _ink_heights_for_motto_lines(lines, font, font_attrib, draw)
    line_gap = int(size_px * (0.32 if not quote_bold else 0.2))
    line_step = max(ink_heights) + max(6, line_gap)
    attrib_idx = _first_attribution_line_index(lines)
    attrib_air = int(size_px * (0.48 if not quote_bold else 0.42))
    _air = attrib_air if attrib_idx is not None else 0
    para_add = attrib_air * len(breaks_before_line)
    trim = max(0, int(size_px * 0.05))
    block_h = (len(lines) - 1) * line_step + max(ink_heights) + _air + para_add - trim
    y0 = text_zone_center - block_h // 2

    def _last_bottom(y0v: int) -> int:
        lb = 0
        for k, ln in enumerate(lines):
            fk = _quote_font_for_line(ln, font, font_attrib)
            bbox = draw.textbbox((0, 0), ln, font=fk)
            ink = bbox[3] - bbox[1]
            pe = _motto_on_scrim_para_extra(k, breaks_before_line, attrib_air)
            y_shift = attrib_air if attrib_idx is not None and k >= attrib_idx else 0
            ty = y0v + k * line_step + pe + y_shift - bbox[1]
            lb = max(lb, ty + ink)
        return lb

    last_bottom = _last_bottom(y0)
    if last_bottom > footer_reserve:
        y0 = max(int(canvas_h * 0.12), int(footer_reserve - last_bottom + y0))
        last_bottom = _last_bottom(y0)

    if quote_bold:
        q_fill, q_stroke = _QUOTE_ON_SCRIM_FILL, _QUOTE_ON_SCRIM_STROKE
        stroke_w = max(1, int(1.55 * scale))
    else:
        q_fill, q_stroke = _QUOTE_ON_SCRIM_FILL_PLAIN, _QUOTE_ON_SCRIM_STROKE_PLAIN
        stroke_w = max(2, min(5, int(0.55 * scale + 1.15)))

    return {
        "y0": y0,
        "line_step": line_step,
        "font": font,
        "font_attrib": font_attrib,
        "quote_bold": quote_bold,
        "size_px": size_px,
        "size_attrib": size_attrib,
        "stroke_w": stroke_w,
        "q_fill": q_fill,
        "q_stroke": q_stroke,
        "attrib_idx": attrib_idx,
        "attrib_air": attrib_air,
        "breaks_before_line": frozenset(breaks_before_line),
        "last_bottom": last_bottom,
        "footer_pad": footer_pad,
    }


def paint_motto_on_scrim_body(
    draw: ImageDraw.ImageDraw,
    canvas_w: int,
    canvas_h: int,
    lines: list[str],
    breaks_before_line: set[int] | frozenset[int],
    size_px: int,
    *,
    attr_suffix: str = "— 每日寄语",
    draw_footer: bool = True,
) -> None:
    """在已有底图 + scrim 上绘制寄语同款正文与页脚（``compose_motto`` 配图分支复用）。"""
    if not lines:
        return
    geo = layout_motto_on_scrim_body(
        draw, canvas_w, canvas_h, lines, breaks_before_line, size_px
    )
    font = geo["font"]
    font_attrib = geo["font_attrib"]
    y0 = geo["y0"]
    line_step = geo["line_step"]
    stroke_w = geo["stroke_w"]
    q_fill = geo["q_fill"]
    q_stroke = geo["q_stroke"]
    attrib_idx = geo["attrib_idx"]
    attrib_air = geo["attrib_air"]
    size_attrib = geo["size_attrib"]
    size_px_e = geo["size_px"]
    breaks = geo["breaks_before_line"]

    for k, ln in enumerate(lines):
        fk = _quote_font_for_line(ln, font, font_attrib)
        bbox = draw.textbbox((0, 0), ln, font=fk)
        tw = bbox[2] - bbox[0]
        tx = (canvas_w - tw) // 2
        pe = _motto_on_scrim_para_extra(k, breaks, attrib_air)
        y_shift = attrib_air if attrib_idx is not None and k >= attrib_idx else 0
        ty = y0 + k * line_step + pe + y_shift - bbox[1]
        sw = (
            max(1, int(stroke_w * size_attrib / max(size_px_e, 1)))
            if _is_attribution_line(ln)
            else stroke_w
        )
        draw.text(
            (tx, ty),
            ln,
            fill=q_fill,
            font=fk,
            stroke_width=sw,
            stroke_fill=q_stroke,
        )

    if draw_footer:
        scale = min(canvas_w, canvas_h) / 600
        footer_y = canvas_h - geo["footer_pad"]
        _draw_motto_footer(
            draw, canvas_w, footer_y, scale, on_scrim=True, attr_suffix=attr_suffix
        )


def motto_on_scrim_body_height(
    draw: ImageDraw.ImageDraw,
    canvas_w: int,
    canvas_h: int,
    lines: list[str],
    breaks_before_line: set[int] | frozenset[int],
    size_px: int,
) -> int:
    """正文块占用高度（用于杂锦等 shrink-to-fit）；与 ``layout_motto_on_scrim_body`` 一致。"""
    geo = layout_motto_on_scrim_body(
        draw, canvas_w, canvas_h, lines, breaks_before_line, size_px
    )
    return max(0, geo["last_bottom"] - geo["y0"])


def motto_on_scrim_body_fits(
    draw: ImageDraw.ImageDraw,
    canvas_w: int,
    canvas_h: int,
    lines: list[str],
    breaks_before_line: set[int] | frozenset[int],
    size_px: int,
) -> bool:
    """正文是否落在与 ``compose_motto`` 配图相同的顶/底安全区内。"""
    if not lines:
        return False
    geo = layout_motto_on_scrim_body(
        draw, canvas_w, canvas_h, lines, breaks_before_line, size_px
    )
    scale = min(canvas_w, canvas_h) / 600
    footer_reserve = canvas_h - max(20, int(26 * scale)) - int(18 * scale)
    return geo["last_bottom"] <= footer_reserve + 1 and geo["y0"] >= int(canvas_h * 0.12) - 2


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

        # 渐变起点高 + 深底色与高峰值透明度，压暗带更实，白字与亮底分离更好。
        scrim_start = int(canvas_h * 0.28)
        overlay_bottom_scrim(
            img,
            scrim_start,
            canvas_h - scrim_start,
            scrim_rgb=(16, 18, 24),
            default_max_opacity=0.88,
            curve_exp=1.30,
        )
        draw = ImageDraw.Draw(img)

        size_px = max(21, int(30 * scale))
        raw_max = max(8, int((canvas_w - margin * 2) / (size_px * 1.02)))
        n = len(motto)
        if n <= raw_max:
            max_chars = n
        elif n <= raw_max * 2:
            max_chars = (n + 1) // 2
        else:
            max_chars = raw_max
        lines = _motto_wrap_pipeline(motto, max_chars=max_chars, max_lines=6)
        paint_motto_on_scrim_body(
            draw,
            canvas_w,
            canvas_h,
            lines,
            frozenset(),
            size_px,
            attr_suffix="— 每日寄语",
            draw_footer=True,
        )

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
        size_attrib = max(16, int(size_px * _MOTTO_ATTRIB_SIZE_RATIO))
        font_attrib, _ = load_motto_quote_font(size_attrib)
        max_chars = max(6, int((canvas_w - margin * 2) / (size_px * 1.02)))
        lines = _motto_wrap_pipeline(motto, max_chars=max_chars, max_lines=6)
        ink_heights = _ink_heights_for_motto_lines(lines, font, font_attrib, draw)
        line_gap2 = int(size_px * (0.30 if not quote_bold else 0.22))
        line_step = max(ink_heights) + max(6, line_gap2)
        attrib_idx2 = _first_attribution_line_index(lines)
        attrib_air2 = int(size_px * (0.46 if not quote_bold else 0.38))
        _air2 = attrib_air2 if attrib_idx2 is not None else 0
        block_h = (len(lines) - 1) * line_step + max(ink_heights) + _air2 - max(0, int(size_px * 0.06))
        y0 = bar_y + bar_h + int(22 * scale)

        tw_off = max(1, int(1.0 * scale))
        text_fill = _TEXT_COLOR if quote_bold else (42, 44, 48)
        for k, ln in enumerate(lines):
            fk = _quote_font_for_line(ln, font, font_attrib)
            bbox = draw.textbbox((0, 0), ln, font=fk)
            tw = bbox[2] - bbox[0]
            tx = (canvas_w - tw) // 2
            y_shift = attrib_air2 if attrib_idx2 is not None and k >= attrib_idx2 else 0
            ty = y0 + k * line_step + y_shift - bbox[1]
            if quote_bold:
                draw.text((tx + tw_off, ty + tw_off), ln, fill=(228, 226, 222), font=fk)
                draw.text((tx, ty), ln, fill=text_fill, font=fk)
            else:
                draw.text((tx, ty), ln, fill=text_fill, font=fk)

        footer_y = y0 + len(lines) * line_step + max(10, int(16 * scale))
        _draw_motto_footer(draw, canvas_w, footer_y, scale, on_scrim=False)

    return img
