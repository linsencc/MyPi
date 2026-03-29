#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
海报布局：上区配图、下区语录 → 1200×1600 竖屏 → 13.3\" e-Paper HAT+ (E6)。

- 默认从同目录 posters.json 随机一条（语录 + 配图 URL + 关键词）。
- --online 从 hitokoto.cn 拉一句热门语录，再按关键词在 posters.json 里选最相关的配图。
- --dry-run 只生成预览 PNG，不碰墨水屏。
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys

from image_fetch import fetch_url_bytes

_W = 1200
_H = 1600
_IMG_H_FRAC = 0.56
_MARGIN_X = 44
_MARGIN_TEXT_TOP = 28
_LINE_GAP = 10
_BYLINE_GAP = 20

_LIB = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "e-Paper",
        "E-paper_Separate_Program",
        "13.3inch_e-Paper_E",
        "RaspberryPi",
        "python",
        "lib",
    )
)
_PIC = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "e-Paper",
        "E-paper_Separate_Program",
        "13.3inch_e-Paper_E",
        "RaspberryPi",
        "python",
        "pic",
    )
)


def _load_rgb(path_or_url: str, use_cache: bool = True) -> "Image.Image":
    from io import BytesIO

    from PIL import Image

    if path_or_url.startswith(("http://", "https://")):
        data = fetch_url_bytes(path_or_url, timeout=120, use_cache=use_cache)
        im = Image.open(BytesIO(data))
    else:
        im = Image.open(path_or_url)
    return im.convert("RGB")


def _font_path() -> str:
    ttc = os.path.join(_PIC, "Font.ttc")
    if os.path.isfile(ttc):
        return ttc
    raise FileNotFoundError(
        "需要中文显示：未找到微雪例程字体 Font.ttc，路径应为：\n" + ttc
    )


def _measure_line(draw, text: str, font) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _wrap_lines(draw, text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for ch in text:
        test = current + ch
        w, _ = _measure_line(draw, test, font)
        if w <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = ch

    if current:
        lines.append(current)
    return lines if lines else [""]


def _layout_text_height(
    lines: list[str], quote_font, byline_font, draw, byline: str
) -> int:
    h = 0
    for ln in lines:
        _, lh = _measure_line(draw, ln, quote_font)
        h += lh + _LINE_GAP
    h -= _LINE_GAP
    h += _BYLINE_GAP
    _, bh = _measure_line(draw, byline, byline_font)
    h += bh
    return h


def _pick_fonts_for_block(
    draw,
    quote: str,
    byline: str,
    text_w: int,
    text_h_max: int,
    font_path: str,
):
    from PIL import ImageFont

    for qsize in range(36, 19, -2):
        bsize = max(18, qsize - 10)
        qf = ImageFont.truetype(font_path, qsize)
        bf = ImageFont.truetype(font_path, bsize)
        lines = _wrap_lines(draw, quote, qf, text_w)
        need = _layout_text_height(lines, qf, bf, draw, byline)
        if need <= text_h_max:
            return qf, bf, lines
    qf = ImageFont.truetype(font_path, 18)
    bf = ImageFont.truetype(font_path, 16)
    lines = _wrap_lines(draw, quote, qf, text_w)
    return qf, bf, lines


def build_poster_rgb(
    quote: str, byline: str, image_url: str, use_cache: bool = True
) -> "Image.Image":
    from PIL import Image, ImageDraw, ImageFont, ImageOps

    img_h = int(_H * _IMG_H_FRAC)
    text_top = img_h + 6
    text_h_avail = _H - text_top - 36

    art = _load_rgb(image_url, use_cache=use_cache)
    art = ImageOps.cover(art, (_W, img_h))
    if art.size != (_W, img_h):
        art = art.resize((_W, img_h), Image.Resampling.LANCZOS)

    canvas = Image.new("RGB", (_W, _H), (255, 255, 255))
    canvas.paste(art, (0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, img_h, _W, img_h + 4), fill=(30, 30, 30))

    font_path = _font_path()
    text_w = _W - 2 * _MARGIN_X
    tmp = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    qf, bf, lines = _pick_fonts_for_block(
        tmp, quote, byline, text_w, text_h_avail - _MARGIN_TEXT_TOP, font_path
    )

    y = text_top + _MARGIN_TEXT_TOP
    for ln in lines:
        lw, lh = _measure_line(draw, ln, qf)
        x = (_W - lw) // 2
        draw.text((x, y), ln, font=qf, fill=(0, 0, 0))
        y += lh + _LINE_GAP

    y += _BYLINE_GAP - _LINE_GAP
    bw, bh = _measure_line(draw, byline, bf)
    draw.text(((_W - bw) // 2, y), byline, font=bf, fill=(60, 60, 120))
    return canvas


def _load_posters(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list) or not data:
        raise ValueError("posters.json 必须是非空数组")
    for i, row in enumerate(data):
        for k in ("quote", "byline"):
            if k not in row:
                raise ValueError(f"posters.json[{i}] 缺少字段 {k}")
        if "image_url" not in row and not row.get("image_file"):
            raise ValueError(f"posters.json[{i}] 需要 image_url 或 image_file")
        row.setdefault("keywords", [])
        row.setdefault("image_url", "")
    return data


def resolve_image_source(
    row: dict, json_dir: str, cli_image: str | None, *, require_usable: bool = True
) -> str:
    """CLI 指定路径优先；否则若存在 image_file 本地文件则用本地；否则 image_url。"""
    if cli_image:
        p = os.path.abspath(cli_image)
        if not os.path.isfile(p):
            raise FileNotFoundError(f"--image 文件不存在: {p}")
        return p
    rel = row.get("image_file")
    if rel:
        local = os.path.join(json_dir, rel)
        if os.path.isfile(local):
            return local
    u = row.get("image_url") or ""
    if u.startswith(("http://", "https://")):
        return u
    if require_usable:
        raise FileNotFoundError(
            "无可用配图：请设置 image_url、放入 image_file 对应文件，或 --prefetch / --image"
        )
    return u


def _keyword_score(keywords: list[str], text: str) -> int:
    if not keywords:
        return 0
    return sum(1 for kw in keywords if kw and kw in text)


def _pick_row_for_quote(posters: list[dict], quote_text: str) -> dict:
    best = max(posters, key=lambda p: _keyword_score(p.get("keywords", []), quote_text))
    if _keyword_score(best.get("keywords", []), quote_text) == 0:
        return random.choice(posters)
    return best


def _fetch_hitokoto(use_cache: bool = True) -> tuple[str, str]:
    u = "https://v1.hitokoto.cn/?encode=json"
    raw = fetch_url_bytes(u, timeout=25, use_cache=use_cache)
    j = json.loads(raw.decode("utf-8"))
    q = (j.get("hitokoto") or "").strip()
    src = (j.get("from") or "").strip()
    who = (j.get("from_who") or "").strip()
    if src and who:
        byline = f"「{src}」{who}"
    elif src:
        byline = f"「{src}」"
    elif who:
        byline = who
    else:
        byline = "一言"
    return q, byline


def main():
    parser = argparse.ArgumentParser(description="海报语录 + 配图 → 13.3 E6 墨水屏")
    parser.add_argument(
        "-j",
        "--json",
        default=os.path.join(os.path.dirname(__file__), "posters.json"),
        help="语录与配图配置 JSON",
    )
    parser.add_argument(
        "--index",
        type=int,
        default=-1,
        help="指定 posters.json 下标（默认随机）",
    )
    parser.add_argument(
        "--online",
        action="store_true",
        help="从 hitokoto.cn 拉语录，配图按关键词匹配 posters.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只写入 poster_preview.png，不刷新墨水屏（屏完全不会变）",
    )
    parser.add_argument(
        "-o",
        "--preview",
        default="",
        help="--dry-run 时预览图路径（默认 digital-frame/poster_preview.png）",
    )
    parser.add_argument(
        "--image",
        default="",
        help="本地配图路径，覆盖 json 中的 URL/文件",
    )
    parser.add_argument(
        "--prefetch",
        action="store_true",
        help="仅预下载 posters.json 中所有 image_url 到 digital-frame/.image-cache/",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="本次下载不读、不写磁盘缓存（仍走 urllib/requests/curl）",
    )
    parser.add_argument(
        "--clear-first",
        action="store_true",
        help="刷屏前先全屏 Clear 一次（多耗一轮刷新，便于确认硬件在动）",
    )
    parser.add_argument(
        "--save-preview",
        action="store_true",
        help="刷新墨水屏的同时把合成结果存成 poster_preview.png",
    )
    args = parser.parse_args()

    posters = _load_posters(args.json)
    json_dir = os.path.dirname(os.path.abspath(args.json))
    use_cache = not args.no_cache
    cli_img = args.image.strip() or None

    if args.prefetch:
        seen: set[str] = set()
        for row in posters:
            u = (row.get("image_url") or "").strip()
            if u.startswith(("http://", "https://")) and u not in seen:
                seen.add(u)
                print("prefetch:", u[:88], "…" if len(u) > 88 else "")
                fetch_url_bytes(u, timeout=120, use_cache=True)
        print("完成，共", len(seen), "个 URL 已缓存。")
        return

    if args.online:
        quote, byline = _fetch_hitokoto(use_cache=use_cache)
        if not quote:
            print("一言接口未返回正文", file=sys.stderr)
            sys.exit(1)
        row = _pick_row_for_quote(posters, quote)
        image_src = resolve_image_source(row, json_dir, cli_img)
        print("在线语录:", quote[:60], "…" if len(quote) > 60 else "")
    else:
        idx = args.index if args.index >= 0 else random.randrange(len(posters))
        row = posters[idx]
        quote = row["quote"]
        byline = row["byline"]
        image_src = resolve_image_source(row, json_dir, cli_img)
        print("条目:", idx, "|", byline)

    print("加载配图…", image_src[:80], "…" if len(image_src) > 80 else "")
    poster = build_poster_rgb(quote, byline, image_src, use_cache=use_cache)

    preview_path = args.preview or os.path.join(
        os.path.dirname(__file__), "poster_preview.png"
    )
    if args.dry_run:
        print(
            "\n*** --dry-run：不会调用墨水屏，只写 PNG。要屏变请去掉 --dry-run ***\n",
            file=sys.stderr,
        )
        poster.save(preview_path, format="PNG")
        print("已保存预览:", preview_path)
        return

    if not os.path.isdir(_LIB):
        print("找不到驱动 lib：", _LIB, file=sys.stderr)
        sys.exit(1)

    sys.path.insert(0, _LIB)
    import epd13in3E

    if args.save_preview:
        poster.save(preview_path, format="PNG")
        print("已同步保存预览:", preview_path)

    epd = epd13in3E.EPD()
    try:
        print(">>> 正在驱动墨水屏硬件刷新（非预览模式）<<<")
        print("初始化墨水屏…")
        epd.Init()
        if args.clear_first:
            print("全屏 Clear（约数十秒）…")
            epd.Clear()
        buf = epd.getbuffer(poster)
        print("刷新海报画面（约数十秒）…")
        epd.display(buf)
        print("完成。墨水屏应已显示本张海报；进入睡眠…")
        epd.sleep()
    except KeyboardInterrupt:
        print("中断，尝试 sleep…", file=sys.stderr)
        try:
            epd.sleep()
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
