"""Extended acceptance: non-blank preview PNG + safe output paths. Run: PYTHONPATH=. python verify_acceptance.py"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from PIL import Image

# Minimum dark pixels: empty/broken CJK renders stay well below this.
_MIN_INK_PIXELS = 800


def main() -> int:
    from app.factory import create_app

    app = create_app()
    c = app.test_client()
    fails = 0

    # --- TC-C02 ---
    r = c.get("/api/v1/scenes/__no_such_scene__")
    if r.status_code != 404:
        print("FAIL TC-C02 scenes 404", r.status_code)
        fails += 1
    else:
        print("OK TC-C02 GET unknown scene -> 404")

    # --- TC-C01 path escape via filename ".." ---
    rid = "00000000-0000-4000-8000-000000000001"
    r = c.get(f"/api/v1/output/{rid}/..")
    if r.status_code != 404:
        print("FAIL TC-C01 output path escape", r.status_code)
        fails += 1
    else:
        print("OK TC-C01 output .. segment -> 404")

    # --- TC-B01 ink after show-now ---
    r = c.get("/api/v1/config")
    cfg = r.get_json()
    if not cfg or not cfg.get("scenes"):
        print("FAIL TC-B01 no config scenes")
        return 1
    sid = cfg["scenes"][0]["id"]
    r = c.post(f"/api/v1/scenes/{sid}/show-now")
    sn = r.get_json()
    if r.status_code != 200 or not sn or not sn.get("ok"):
        print("FAIL TC-B01 show-now", r.status_code, sn)
        return 1
    prev = None
    deadline = time.time() + 45.0
    while time.time() < deadline:
        r2 = c.get("/api/v1/wall/state")
        ws = r2.get_json()
        prev = (ws or {}).get("currentPreviewUrl")
        if prev and str(prev).startswith("/api/v1/output/"):
            break
        time.sleep(0.05)
    if not prev:
        print("FAIL TC-B01 no preview url after wait")
        return 1
    r = c.get(prev)
    if r.status_code != 200:
        print("FAIL TC-B01 fetch PNG", r.status_code, prev)
        return 1
    tmp = Path(__import__("tempfile").mkdtemp()) / "frame.png"
    tmp.write_bytes(r.data)
    im = Image.open(tmp).convert("RGB")
    px = im.load()
    w, h = im.size
    ink = sum(1 for y in range(h) for x in range(w) if sum(px[x, y]) < 200)
    print("TC-B01 dark_pixels_lt200", ink, "(min", _MIN_INK_PIXELS, ")")
    if ink < _MIN_INK_PIXELS:
        print("FAIL TC-B01 insufficient ink (font / blank render?)")
        fails += 1
    else:
        print("OK TC-B01 CJK render ink")

    if fails:
        print("RESULT: FAIL", fails)
        return 1
    print("RESULT: OK verify_acceptance")
    return 0


if __name__ == "__main__":
    sys.exit(main())
