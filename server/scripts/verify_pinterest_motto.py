#!/usr/bin/env python3
"""Smoke-test Pinscrape fetch for ai_motto (run on Pi with same env as mypi.service)."""

from __future__ import annotations

import os
import sys

# Repo root: server/scripts -> parent is server
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from renderers.templates.ai_motto.images import fetch_web_motto_image  # noqa: E402


def main() -> int:
    flag = os.environ.get("MYPI_MOTTO_PINSCRAPE", "").strip().lower()
    if flag in ("0", "false", "no", "off"):
        print("MYPI_MOTTO_PINSCRAPE is off; enable pinscrape for this smoke test.")
        return 2
    prompt = (
        "watercolor mountain lake autumn forest scenic wallpaper "
        "colorful soft golden light painterly aesthetic landscape"
    )
    im = fetch_web_motto_image(prompt, 800, 600, "verify_pinscrape_motto")
    if im is None:
        print("FETCH: failed (pinscrape returned no image; check proxy / pip install pinscrape)")
        return 1
    print("FETCH: ok mode=%s size=%sx%s" % (im.mode, im.width, im.height))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
