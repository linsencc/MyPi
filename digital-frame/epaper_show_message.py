#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 13.3″ e-Paper (E) 上显示一句寄语（树莓派上运行）。注重留白与垂直节奏。"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 1600

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_EPAPER = (
    _SCRIPT_DIR.parent
    / "e-Paper"
    / "E-paper_Separate_Program"
    / "13.3inch_e-Paper_E"
    / "RaspberryPi"
    / "python"
)
_LIB = _REPO_EPAPER / "lib"
_PIC = _REPO_EPAPER / "pic"
_LIB_FALLBACK = Path.home() / "workspace/e-Paper/E-paper_Separate_Program/13.3inch_e-Paper_E/RaspberryPi/python/lib"

_MARGIN_X = 96
_LINE_GAP = 14
_PAR_BREAK = 36
_TITLE_RULE_GAP = 20
_RULE_BODY_GAP = 36
_SIG_BODY_GAP = 48

DEFAULT_KICKER = "今 日 寄 语"

DEFAULT_LINES = [
    "你此刻愿意向前迈出一小步，",
    "已经超过了停在原地的许多人。",
    "",
    "路长不怕，只怕心冷。",
    "允许自己慢一点，但请别轻易说「算了」。",
    "",
    "下一步里，藏着你的答案。",
    "",
    "—— MyPi · 与你同行",
]


def _lib_path() -> Path:
    if _LIB.is_dir():
        return _LIB
    if _LIB_FALLBACK.is_dir():
        return _LIB_FALLBACK
    return _LIB


def _font_path(cli: str) -> str:
    if cli and Path(cli).is_file():
        return cli
    noto = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    if Path(noto).is_file():
        return noto
    ttc = str(_PIC / "Font.ttc")
    if Path(ttc).is_file():
        return ttc
    raise FileNotFoundError(
        "未找到中文字体。请安装 noto fonts 或使用 --font 指定路径。"
    )


def _measure_line(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _wrap_line(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int
) -> list[str]:
    text = text.strip()
    if not text:
        return []
    out: list[str] = []
    cur = ""
    for ch in text:
        test = cur + ch
        w, _ = _measure_line(draw, test, font)
        if w <= max_w:
            cur = test
        else:
            if cur:
                out.append(cur)
            cur = ch
    if cur:
        out.append(cur)
    return out


def _split_kicker_and_rest(lines: list[str]) -> tuple[str, list[str]]:
    if lines and lines[-1].startswith("——"):
        sig = lines[-1]
        body = lines[:-1]
    else:
        sig = ""
        body = list(lines)
    return sig, body


def _build_body_rows(
    draw: ImageDraw.ImageDraw,
    body_lines: list[str],
    font_body: ImageFont.FreeTypeFont,
    max_w: int,
) -> list[tuple[str, bool]]:
    """返回 (行文本, 是否段后留白)。"""
    rows: list[tuple[str, bool]] = []
    for i, raw in enumerate(body_lines):
        is_blank = raw.strip() == ""
        if is_blank:
            rows.append(("", True))
            continue
        wrapped = _wrap_line(draw, raw, font_body, max_w)
        for j, ln in enumerate(wrapped):
            is_last_in_block = j == len(wrapped) - 1
            next_blank = (
                i + 1 < len(body_lines) and body_lines[i + 1].strip() == ""
            )
            rows.append((ln, is_last_in_block and next_blank))
    return rows


def _content_height(
    draw: ImageDraw.ImageDraw,
    kicker: str,
    rows: list[tuple[str, bool]],
    sig: str,
    font_kicker: ImageFont.FreeTypeFont,
    font_body: ImageFont.FreeTypeFont,
    font_sig: ImageFont.FreeTypeFont,
) -> int:
    h = 0
    _, kh = _measure_line(draw, kicker, font_kicker)
    h += kh + _TITLE_RULE_GAP + 3 + _RULE_BODY_GAP
    for ln, para_break in rows:
        if ln == "" and para_break:
            h += _PAR_BREAK
            continue
        _, bh = _measure_line(draw, ln or " ", font_body)
        h += bh + _LINE_GAP
        if para_break:
            h += _PAR_BREAK - _LINE_GAP
    h -= _LINE_GAP
    if sig:
        h += _SIG_BODY_GAP
        _, sh = _measure_line(draw, sig, font_sig)
        h += sh
    return h


def render_rgb(
    *,
    kicker: str,
    lines: list[str],
    font_path: str,
) -> Image.Image:
    sig, body = _split_kicker_and_rest(lines)

    im = Image.new("RGB", (W, H), (252, 251, 248))
    draw = ImageDraw.Draw(im)

    font_kicker = ImageFont.truetype(font_path, 34)
    font_body = ImageFont.truetype(font_path, 50)
    font_sig = ImageFont.truetype(font_path, 34)

    max_w = W - 2 * _MARGIN_X
    rows = _build_body_rows(draw, body, font_body, max_w)
    total_h = _content_height(
        draw, kicker, rows, sig, font_kicker, font_body, font_sig
    )
    y = max(72, (H - total_h) // 2)

    kw, kh = _measure_line(draw, kicker, font_kicker)
    draw.text(
        ((W - kw) // 2, y),
        kicker,
        font=font_kicker,
        fill=(110, 108, 102),
    )
    y += kh + _TITLE_RULE_GAP

    rule_w = min(720, W - 2 * _MARGIN_X)
    x0 = (W - rule_w) // 2
    draw.line((x0, y, x0 + rule_w, y), fill=(190, 186, 178), width=2)
    y += 3 + _RULE_BODY_GAP

    for ln, para_break in rows:
        if ln == "" and para_break:
            y += _PAR_BREAK
            continue
        w, bh = _measure_line(draw, ln, font_body)
        draw.text(
            ((W - w) // 2, y),
            ln,
            font=font_body,
            fill=(28, 28, 32),
        )
        y += bh + _LINE_GAP
        if para_break:
            y += _PAR_BREAK - _LINE_GAP

    if sig:
        y += _SIG_BODY_GAP - _LINE_GAP
        sw, sh = _measure_line(draw, sig, font_sig)
        draw.text(
            ((W - sw) // 2, y),
            sig,
            font=font_sig,
            fill=(90, 88, 84),
        )

    return im


def main():
    parser = argparse.ArgumentParser(description="在墨水屏上显示寄语（竖屏排版）")
    parser.add_argument("--font", default="", help="字体路径（默认可用 Noto 或例程 Font.ttc）")
    parser.add_argument("--kicker", default=DEFAULT_KICKER, help="顶部小标题")
    parser.add_argument(
        "--message",
        default="",
        help="整段文字，用 \\n 分行；末行以 —— 开头则作为落款",
    )
    parser.add_argument(
        "--dry-run",
        metavar="FILE.png",
        default="",
        help="只生成 PNG 预览，不驱动墨水屏",
    )
    parser.add_argument(
        "--clear-first",
        action="store_true",
        help="刷屏前先全屏 Clear（多一轮刷新，画面卡住或未变时优先试这个）",
    )
    parser.add_argument(
        "--save-preview",
        metavar="FILE.png",
        default="",
        help="上屏同时把当前排版存成 PNG，便于在 Pi 上核对是否已渲染",
    )
    args = parser.parse_args()

    lib = _lib_path()
    if not args.dry_run and not lib.is_dir():
        print("找不到 e-Paper 驱动 lib:", lib, file=sys.stderr)
        print(
            "请把整个 MyPi 同步到树莓派（含 e-Paper/.../python/lib），"
            "或把官方例程放到:",
            _LIB_FALLBACK,
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        font_path = _font_path(args.font)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    lines = (
        [s for s in args.message.splitlines()]
        if args.message
        else list(DEFAULT_LINES)
    )
    im = render_rgb(kicker=args.kicker, lines=lines, font_path=font_path)
    if im.mode != "RGB":
        im = im.convert("RGB")
    if im.size != (W, H):
        im = im.resize((W, H), Image.Resampling.LANCZOS)

    if args.dry_run:
        print(
            "\n*** --dry-run：不会调用墨水屏，只写 PNG。要屏上变化请去掉 --dry-run ***\n",
            file=sys.stderr,
        )
        out = Path(args.dry_run)
        im.save(out, format="PNG")
        print("已写入预览:", out.resolve(), flush=True)
        return

    sys.path.insert(0, str(lib))
    import epd13in3E  # noqa: E402

    if args.save_preview:
        prev = Path(args.save_preview)
        im.save(prev, format="PNG")
        print("已保存排版预览:", prev.resolve(), flush=True)

    epd = epd13in3E.EPD()
    try:
        print(">>> 正在驱动墨水屏硬件刷新（非预览模式）<<<", flush=True)
        print("使用驱动目录:", lib.resolve(), flush=True)
        print("图像:", im.mode, im.size[0], "×", im.size[1], flush=True)
        print("初始化墨水屏…", flush=True)
        epd.Init()
        if args.clear_first:
            print("全屏 Clear（约数十秒）…", flush=True)
            epd.Clear()
        buf = epd.getbuffer(im)
        print("刷新画面（约数十秒）…如仍未变化，请确认 SPI 已开、与 show_masterpiece.py 同一接线。", flush=True)
        epd.display(buf)
        print("完成。墨水屏应已更新；进入睡眠…", flush=True)
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
