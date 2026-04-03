#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公版名画 → 1200×1600 竖屏 → 13.3\" e-Paper HAT+ (E6)."""
import argparse
import os
import sys

from image_fetch import fetch_url_bytes

_W = 1200
_H = 1600

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
sys.path.insert(0, _LIB)

# 维米尔《持水壶的年轻女子》，竖构图；Met Museum Open Access（公版，直连稳定）
# Wikimedia 缩略图链易 429，故默认不用 Commons
DEFAULT_URL = "https://images.metmuseum.org/CRDImages/ep/original/DP353257.jpg"


def _load_rgb(path_or_url: str, *, use_cache: bool = True):
    from io import BytesIO

    from PIL import Image

    if path_or_url.startswith(("http://", "https://")):
        data = fetch_url_bytes(path_or_url, timeout=120, use_cache=use_cache)
        im = Image.open(BytesIO(data))
    else:
        im = Image.open(path_or_url)
    return im.convert("RGB")


def _portrait_cover(im, w: int, h: int):
    from PIL import ImageOps

    return ImageOps.cover(im, (w, h))


def _portrait_contain_on_white(im, w: int, h: int):
    """完整图可见、不足处留白（适合带底部文字的拼图 / 海报）。"""
    from PIL import Image, ImageOps

    fitted = ImageOps.contain(im, (w, h), method=Image.Resampling.LANCZOS)
    out = Image.new("RGB", (w, h), (255, 255, 255))
    x = (w - fitted.width) // 2
    y = (h - fitted.height) // 2
    out.paste(fitted, (x, y))
    return out


def main():
    parser = argparse.ArgumentParser(description="名画显示到 13.3 E6 墨水屏（竖屏）")
    parser.add_argument(
        "-u",
        "--url",
        default=DEFAULT_URL,
        help="图片 URL 或本地路径",
    )
    parser.add_argument(
        "-o",
        "--cache",
        default="",
        help="可选：先保存下载到该路径再显示",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="本次不读、不写下载缓存",
    )
    parser.add_argument(
        "--clear-first",
        action="store_true",
        help="刷屏前先全屏 Clear 一次（多一轮刷新）",
    )
    parser.add_argument(
        "--contain",
        action="store_true",
        help="按长边适配画布并居中留白（不裁切）；默认铺满裁切 (cover)",
    )
    args = parser.parse_args()

    if not os.path.isdir(_LIB):
        print("找不到驱动 lib：", _LIB, file=sys.stderr)
        sys.exit(1)

    import epd13in3E
    from PIL import Image

    print("加载图像…", args.url[:80], "…" if len(args.url) > 80 else "")
    rgb = _load_rgb(args.url, use_cache=not args.no_cache)
    frame = (
        _portrait_contain_on_white(rgb, _W, _H)
        if args.contain
        else _portrait_cover(rgb, _W, _H)
    )
    if frame.size != (_W, _H):
        frame = frame.resize((_W, _H), Image.Resampling.LANCZOS)

    if args.cache:
        os.makedirs(os.path.dirname(os.path.abspath(args.cache)) or ".", exist_ok=True)
        frame.save(args.cache, format="JPEG", quality=92)
        print("已缓存:", args.cache)

    epd = epd13in3E.EPD()
    try:
        print(">>> 正在驱动墨水屏硬件刷新 <<<")
        print("初始化墨水屏…")
        epd.Init()
        if args.clear_first:
            print("全屏 Clear（约数十秒）…")
            epd.Clear()
        buf = epd.getbuffer(frame)
        print("刷新画面（约数十秒）…")
        epd.display(buf)
        print("完成。墨水屏应已更新；进入睡眠…")
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
