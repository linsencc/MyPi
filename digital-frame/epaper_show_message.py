#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 13.3″ e-Paper (E) 上显示一句寄语（树莓派上运行）。"""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 1600
LIB = (
    Path.home()
    / "workspace/e-Paper/E-paper_Separate_Program/13.3inch_e-Paper_E/RaspberryPi/python/lib"
)
sys.path.insert(0, str(LIB))
import epd13in3E  # noqa: E402

DEFAULT_FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"

DEFAULT_LINES = [
    "你今天愿意动手把事情做成，",
    "已经超过很多人停在原地的勇气。",
    "",
    "不必一次完美。",
    "下一步，永远比空想更接近答案。",
    "",
    "—— 替你高兴的你这边的助手",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--font", default=DEFAULT_FONT)
    parser.add_argument("--message", default="", help="整段文字，用 \\n 分行")
    args = parser.parse_args()

    lines = (
        [s for s in args.message.splitlines()] if args.message else list(DEFAULT_LINES)
    )
    font_path = args.font
    if not Path(font_path).is_file():
        print("找不到字体:", font_path, file=sys.stderr)
        sys.exit(1)
    if not LIB.is_dir():
        print("找不到驱动 lib:", LIB, file=sys.stderr)
        sys.exit(1)

    im = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(im)
    font = ImageFont.truetype(font_path, 52)
    small = ImageFont.truetype(font_path, 36)

    if lines and lines[-1].startswith("——"):
        sig = lines[-1]
        body_lines = lines[:-1]
    else:
        sig = ""
        body_lines = lines

    text = "\n".join(body_lines)
    main_spacing = 18
    y0 = 100
    draw.multiline_text(
        (W // 2, y0),
        text,
        font=font,
        fill=(20, 20, 20),
        spacing=main_spacing,
        anchor="ma",
        align="center",
    )
    if sig:
        draw.text((W // 2, H - 120), sig, font=small, fill=(60, 60, 60), anchor="mm")

    epd = epd13in3E.EPD()
    epd.Init()
    buf = epd.getbuffer(im)
    print("刷新画面（墨水屏较慢，请稍候）…", flush=True)
    epd.display(buf)
    epd.sleep()
    print("完成。", flush=True)


if __name__ == "__main__":
    main()
