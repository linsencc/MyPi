"""画板：最终是位图 PNG 上屏，无法使用浏览器 CSS。

用 PIL 模拟常见「卡片 UI」：纵向渐变底、顶区 hero 面板、分区圆角卡片 +
弱投影、左侧色条、区块符号字，尽量在电子墨水对比度下仍清晰。"""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from renderers.templates.cjk_font import _load_cjk_font
from renderers.templates.cn_date import cn_date_str

from . import weather

# 页面与分区（类比浅色主题 + surface 卡片）
_PAGE_GRAD_TOP = (234, 241, 252)
_PAGE_GRAD_BOT = (252, 247, 238)
_HERO_FILL = (255, 253, 250)
_HERO_EDGE = (218, 226, 240)
_PANEL = (248, 250, 255)
_PANEL_EDGE = (200, 210, 228)
_PANEL_SHADOW = (210, 214, 224)
_TITLE = (22, 28, 42)
_SUBTITLE = (88, 94, 108)
_BODY = (34, 40, 52)
_MUTED = (108, 114, 128)
_ACCENT = (42, 78, 168)
_ACCENT_ICON = (55, 95, 190)
_RULE = (58, 64, 76)
_FOOTER_BAR = (216, 220, 230)
_RAIL = (55, 88, 168)

_SECTION_GLYPH: dict[str, str] = {
    "天气": "▸",
    "活动": "●",
    "出行提示": "※",
}

# 面板内左侧色条 + 留白（与测量、绘制一致）
_RAIL_W = 5
_RAIL_GAP = 10


def _fill_vertical_gradient_bands(im: Image.Image, top: tuple[int, int, int], bot: tuple[int, int, int]) -> None:
    """分水平条插值，比逐像素快，适合树莓派。"""
    d = ImageDraw.Draw(im)
    w, h = im.size
    band = max(3, min(8, h // 100))
    hm = max(1, h - band)
    y0 = 0
    while y0 < h:
        t = min(1.0, y0 / hm)
        r = int(top[0] * (1 - t) + bot[0] * t)
        g = int(top[1] * (1 - t) + bot[1] * t)
        b = int(top[2] * (1 - t) + bot[2] * t)
        y1 = min(h, y0 + band)
        d.rectangle([0, y0, w, y1], fill=(r, g, b))
        y0 = y1


def _panel_content_offset(pad: int) -> int:
    """正文区相对面板左内边距的偏移（色条 + 间隙 + 对齐）。"""
    return pad + _RAIL_W + _RAIL_GAP + 4


def _panel_body_text_width(inner_w: int, pad: int) -> int:
    return max(40, inner_w - _panel_content_offset(pad) - pad)

_BREAK_AFTER = frozenset("，、；。：！？．!?,)）】』〉》…—　 \t")


def _elide(s: str, max_chars: int) -> str:
    t = s.replace("\n", " ").strip()
    if len(t) <= max_chars:
        return t
    return t[: max(1, max_chars - 1)] + "…"


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> float:
    if hasattr(draw, "textlength"):
        try:
            return float(draw.textlength(text, font=font))
        except (TypeError, ValueError):
            pass
    b = draw.textbbox((0, 0), text, font=font)
    return float(b[2] - b[0])


def _line_height(draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont) -> int:
    b = draw.textbbox((0, 0), "国Ag", font=font)
    return max(1, b[3] - b[1])


def _wrap_line(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int) -> list[str]:
    t = text.replace("\n", " ").strip()
    if not t:
        return []
    if _text_width(draw, t, font) <= max_w:
        return [t]
    lines: list[str] = []
    pos = 0
    while pos < len(t):
        lo, hi = pos + 1, len(t)
        best = pos + 1
        while lo <= hi:
            mid = (lo + hi) // 2
            chunk = t[pos:mid]
            if _text_width(draw, chunk, font) <= max_w:
                best = mid
                lo = mid + 1
            else:
                hi = mid - 1
        if best <= pos:
            best = pos + 1
        cut = best
        for j in range(best, pos, -1):
            if j < len(t) and t[j - 1] in _BREAK_AFTER:
                cut = j
                break
        if cut <= pos:
            cut = pos + 1
        lines.append(t[pos:cut].strip())
        pos = cut
    return [ln for ln in lines if ln]


def _rounded_panel(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    *,
    radius: int,
    fill: tuple[int, int, int],
    outline: tuple[int, int, int],
) -> None:
    x0, y0, x1, y1 = box
    if hasattr(draw, "rounded_rectangle"):
        draw.rounded_rectangle(
            [x0, y0, x1, y1], radius=radius, fill=fill, outline=outline, width=1
        )
    else:
        draw.rectangle([x0, y0, x1, y1], fill=fill, outline=outline)


def _panel_block_height(
    draw: ImageDraw.ImageDraw,
    *,
    inner_w: int,
    sec_sz: int,
    bs: int,
    pad: int,
    line_gap: int,
    lines: list[str],
) -> int:
    body_f = _load_cjk_font(bs)
    tw = _panel_body_text_width(inner_w, pad)
    block = pad * 2 + sec_sz + line_gap
    for ln in lines:
        for wl in _wrap_line(draw, ln, body_f, tw):
            block += _line_height(draw, body_f) + line_gap
    return block + pad


def _measure_all_panels(
    draw: ImageDraw.ImageDraw,
    *,
    inner_w: int,
    sec_sz: int,
    bs: int,
    pad: int,
    line_gap: int,
    section_gap: int,
    digest: weather.WeatherDigest | None,
    event_lines: list[str],
    rule: str,
    llm_tip: str | None,
    title_chars: int,
) -> int:
    """所有分区卡片高度 + 间距。"""
    h = 0
    sections = _section_content(digest, event_lines, rule, llm_tip, title_chars)
    for i, (_label, lines) in enumerate(sections):
        if i:
            h += section_gap
        h += _panel_block_height(
            draw,
            inner_w=inner_w,
            sec_sz=sec_sz,
            bs=bs,
            pad=pad,
            line_gap=line_gap,
            lines=lines,
        )
    return h


def _section_content(
    digest: weather.WeatherDigest | None,
    event_lines: list[str],
    rule: str,
    llm_tip: str | None,
    title_chars: int,
) -> list[tuple[str, list[str]]]:
    out: list[tuple[str, list[str]]] = []
    if digest and len(digest.lines) > 1:
        out.append(("天气", list(digest.lines[1:])))
    else:
        out.append(("天气", ["（天气暂不可用，请检查网络）"]))

    if event_lines:
        out.append(("活动", [f"{i}. {_elide(t, title_chars)}" for i, t in enumerate(event_lines, start=1)]))
    else:
        out.append(
            (
                "活动",
                [
                    "暂无活动条目。请配置与每日寄语相同的 MYPI_LLM_* 后重试，或在「我想去的活动」里手动填写（分号分隔）。"
                ],
            )
        )

    tip0 = rule.replace("【提示】", "", 1).strip() if rule.startswith("【提示】") else rule
    tip_lines = [tip0]
    if llm_tip and llm_tip.strip():
        tip_lines.append("小结：" + _elide(llm_tip.strip(), title_chars + 10))
    out.append(("出行提示", tip_lines))
    return out


def render_weekend_card(
    *,
    width: int,
    height: int,
    digest: weather.WeatherDigest | None,
    event_lines: list[str],
    source_labels: list[str],
    rule: str,
    llm_tip: str | None,
    title_chars_per_line: int,
    area_label: str = "深圳",
) -> Image.Image:
    w, h = max(200, width), max(200, height)
    scratch = Image.new("RGB", (w, h), color=_PAGE_GRAD_TOP)
    d0 = ImageDraw.Draw(scratch)

    scale = min(w, h) / 600.0
    margin = max(18, int(w * 0.05))
    footer_h = max(30, int(28 * scale))
    content_bottom = h - margin - footer_h

    title_sz = max(24, int(32 * scale))
    sub_sz = max(12, int(14 * scale))
    sec_sz = max(15, int(18 * scale))
    body_sz = max(13, int(17 * scale))
    pad = max(8, int(10 * scale))
    line_gap = max(5, int(body_sz * 0.34))
    inner_w = w - margin * 2
    radius = max(10, int(12 * scale))

    sub_f_probe = _load_cjk_font(sub_sz)
    sub_h_probe = _line_height(d0, sub_f_probe)
    bar_h_est = max(3, int(4 * scale))
    accent_gap = int(8 * scale)
    post_accent_gap = int(14 * scale)
    by0 = int(margin + title_sz + 2 + sub_h_probe + accent_gap)
    band_y = int(by0 + bar_h_est + post_accent_gap)

    section_gap = max(10, int(8 * scale))
    bs = body_sz
    while bs >= 11:
        total = _measure_all_panels(
            d0,
            inner_w=inner_w,
            sec_sz=sec_sz,
            bs=bs,
            pad=pad,
            line_gap=line_gap,
            section_gap=section_gap,
            digest=digest,
            event_lines=event_lines,
            rule=rule,
            llm_tip=llm_tip,
            title_chars=title_chars_per_line,
        )
        avail = content_bottom - band_y - int(14 * scale)
        if total <= avail + 8 or bs <= 11:
            break
        bs -= 1

    img = Image.new("RGB", (w, h), color=_PAGE_GRAD_TOP)
    _fill_vertical_gradient_bands(img, _PAGE_GRAD_TOP, _PAGE_GRAD_BOT)
    draw = ImageDraw.Draw(img)
    title_f = _load_cjk_font(title_sz)
    sub_f = _load_cjk_font(sub_sz)
    sec_f = _load_cjk_font(sec_sz)
    body_f = _load_cjk_font(bs)

    hero_r = radius + int(8 * scale)
    hero_top = max(4, margin - int(14 * scale))
    hero_bot = band_y + int(12 * scale)
    hx0 = margin - int(6 * scale)
    hx1 = w - margin + int(6 * scale)
    _rounded_panel(
        draw,
        (hx0, hero_top, hx1, hero_bot),
        radius=hero_r,
        fill=_HERO_FILL,
        outline=_HERO_EDGE,
    )

    title = "周末出行"
    tw = _text_width(draw, title, title_f)
    draw.text(((w - tw) / 2, margin), title, fill=_TITLE, font=title_f)
    sub = f"{(area_label or '深圳').strip() or '深圳'} · 出行简报"
    sw = _text_width(draw, sub, sub_f)
    draw.text(((w - sw) / 2, margin + title_sz + 2), sub, fill=_SUBTITLE, font=sub_f)

    bar_w = min(int(inner_w * 0.44), int(240 * scale))
    bar_h = bar_h_est
    cx = w / 2.0
    bx0 = int(cx - bar_w / 2)
    if hasattr(draw, "rounded_rectangle"):
        draw.rounded_rectangle(
            [bx0, by0, bx0 + bar_w, by0 + bar_h],
            radius=max(2, bar_h // 2),
            fill=_ACCENT,
        )
    else:
        draw.rectangle([bx0, by0, bx0 + bar_w, by0 + bar_h], fill=_ACCENT)

    div_w = max(1, int(2 * scale))
    draw.line([(margin, band_y), (w - margin, band_y)], fill=_FOOTER_BAR, width=div_w)

    total_h = _measure_all_panels(
        draw,
        inner_w=inner_w,
        sec_sz=sec_sz,
        bs=bs,
        pad=pad,
        line_gap=line_gap,
        section_gap=section_gap,
        digest=digest,
        event_lines=event_lines,
        rule=rule,
        llm_tip=llm_tip,
        title_chars=title_chars_per_line,
    )
    avail = content_bottom - band_y - int(12 * scale)
    y = band_y + max(0, int((avail - total_h) * 0.28))

    max_text_w = _panel_body_text_width(inner_w, pad)
    tx_content = margin + _panel_content_offset(pad)
    icon_sz = max(sec_sz + 2, int(20 * scale))
    gap_ico = max(6, int(8 * scale))

    for si, (label, lines) in enumerate(
        _section_content(digest, event_lines, rule, llm_tip, title_chars_per_line)
    ):
        if si:
            y += section_gap
        block_h = _panel_block_height(
            draw,
            inner_w=inner_w,
            sec_sz=sec_sz,
            bs=bs,
            pad=pad,
            line_gap=line_gap,
            lines=lines,
        )
        y1 = y + block_h
        sh = max(2, int(3 * scale))
        _rounded_panel(
            draw,
            (margin + sh, y + sh, w - margin + sh, y1 + sh),
            radius=radius,
            fill=_PANEL_SHADOW,
            outline=_PANEL_SHADOW,
        )
        _rounded_panel(
            draw,
            (margin, y, w - margin, y1),
            radius=radius,
            fill=_PANEL,
            outline=_PANEL_EDGE,
        )
        rx0 = margin + pad
        rx1 = rx0 + _RAIL_W
        ry0 = int(y + pad * 0.75)
        ry1 = int(y1 - pad * 0.75)
        if ry1 > ry0 + 6:
            rrail = max(2, _RAIL_W // 2)
            if hasattr(draw, "rounded_rectangle"):
                draw.rounded_rectangle([rx0, ry0, rx1, ry1], radius=rrail, fill=_RAIL)
            else:
                draw.rectangle([rx0, ry0, rx1, ry1], fill=_RAIL)

        ty = y + pad
        icon_f = _load_cjk_font(icon_sz)
        glyph = _SECTION_GLYPH.get(label, "·")
        gw = int(_text_width(draw, glyph, icon_f))
        iy = ty + max(0, int((sec_sz - icon_sz) * 0.25))
        draw.text((tx_content, iy), glyph, fill=_ACCENT_ICON, font=icon_f)
        draw.text((tx_content + gw + gap_ico, ty), label, fill=_ACCENT, font=sec_f)
        ty += sec_sz + line_gap
        for ln in lines:
            for wl in _wrap_line(draw, ln, body_f, max_text_w):
                bh = _line_height(draw, body_f)
                if ty + bh > y1 - pad:
                    wl = _elide(wl, max(8, int(max_text_w / max(7.0, bs * 0.9))))
                fill = _RULE if label == "出行提示" else _BODY
                draw.text((tx_content, ty), wl, fill=fill, font=body_f)
                ty += bh + line_gap
        y = y1

    src = "、".join(dict.fromkeys(source_labels)) if source_labels else "无"
    foot_raw = f"{cn_date_str()}　·　活动：{src}　·　仅供参考　·　天气 Open-Meteo"
    small = _load_cjk_font(max(10, int(12 * scale)))
    max_fw = inner_w - 8
    mc = len(foot_raw)
    foot = foot_raw
    while mc >= 6 and _text_width(draw, _elide(foot_raw, mc), small) > max_fw:
        mc -= 1
    foot = _elide(foot_raw, mc)
    fb = draw.textbbox((0, 0), foot, font=small)
    fy = h - margin - (fb[3] - fb[1])
    draw.line([(margin, fy - 8), (w - margin, fy - 8)], fill=_FOOTER_BAR, width=1)
    draw.text((margin, fy), foot, fill=_MUTED, font=small)

    return img
