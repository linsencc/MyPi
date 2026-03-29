#!/usr/bin/env bash
# 运行微雪 13.3" E 系官方 Python demo（依赖 ~/workspace/e-Paper 已存在）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEMO_DIR="$ROOT/e-Paper/E-paper_Separate_Program/13.3inch_e-Paper_E/RaspberryPi/python/examples"
if [[ ! -f "$DEMO_DIR/epd_13in3E_test.py" ]]; then
  echo "未找到例程: $DEMO_DIR/epd_13in3E_test.py" >&2
  echo "请先在本机克隆或保留 waveshareteam/e-Paper 仓库至 $ROOT/e-Paper" >&2
  exit 1
fi
export PYTHONUNBUFFERED=1
cd "$DEMO_DIR"
exec python3 epd_13in3E_test.py "$@"
