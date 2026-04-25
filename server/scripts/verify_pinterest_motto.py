#!/usr/bin/env python3
"""Smoke-test Pinterest fetch for ai_motto (run on Pi with same env as mypi.service)."""

from __future__ import annotations

import os
import sys

# Repo root: server/scripts -> parent is server
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from renderers.templates.ai_motto.images import (  # noqa: E402
    fetch_pinterest_motto_image,
    pinterest_access_token,
)


def main() -> int:
    tok = pinterest_access_token()
    if not tok:
        print("PINTEREST_TOKEN: MISSING (set MYPI_PINTEREST_ACCESS_TOKEN or PINTEREST_ACCESS_TOKEN)")
        return 2
    print("PINTEREST_TOKEN: set (length %d)" % len(tok))
    prompt = (
        "watercolor mountain lake autumn forest scenic wallpaper "
        "colorful soft golden light painterly aesthetic landscape"
    )
    im = fetch_pinterest_motto_image(prompt, "verify_pinterest_motto")
    if im is None:
        print("FETCH: failed (no image after Pinterest attempts)")
        return 1
    print("FETCH: ok mode=%s size=%sx%s" % (im.mode, im.width, im.height))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
