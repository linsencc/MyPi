#!/bin/sh
# 顺德拼图 → 13.3″ E6 竖屏（树莓派上执行，需SPI与驱动已就绪）
cd "$(dirname "$0")"
exec python3 show_masterpiece.py -u images/shunde-city-sounds.png --contain "$@"
