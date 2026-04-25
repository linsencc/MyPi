"""Download Wikimedia originals into renderers/templates/masterpieces/ (run once from dev machine).

Usage (from server/):  PYTHONPATH=. python scripts/fetch_world_masterpiece_assets.py
"""
from __future__ import annotations

import io
import os
import sys
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "renderers" / "templates" / "masterpieces"
UA = "MyPiWallDisplay/1.0 (asset fetch; +https://github.com/)"
_COMMONS = "https://upload.wikimedia.org/wikipedia/commons/"


def _thumb_urls(direct: str) -> list[str]:
    """Prefer scaled thumbs (small, reliable); fall back to direct."""
    out: list[str] = []
    if "/thumb/" not in direct and direct.startswith(_COMMONS):
        rest = direct[len(_COMMONS) :]
        parts = rest.split("/", 2)
        if len(parts) == 3:
            a, b, fname = parts
            for w in (1024, 800, 640):
                out.append(f"{_COMMONS}thumb/{a}/{b}/{fname}/{w}px-{fname}")
    out.append(direct)
    return out


def _all_fetch_urls(direct: str) -> list[str]:
    """Thumbs, then Special:FilePath redirect, then direct."""
    fname = direct.rsplit("/", 1)[-1]
    fp = f"https://commons.wikimedia.org/wiki/Special:FilePath/{fname}"
    seen: set[str] = set()
    out: list[str] = []
    for u in _thumb_urls(direct) + [fp]:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


# (filename, direct Commons URL — script derives thumb URLs)
ASSETS: tuple[tuple[str, str], ...] = (
    ("starry_night.jpg", "https://upload.wikimedia.org/wikipedia/commons/e/ea/Van_Gogh_-_Starry_Night_-_Google_Art_Project.jpg"),
    ("mona_lisa.jpg", "https://upload.wikimedia.org/wikipedia/commons/e/ec/Mona_Lisa%2C_by_Leonardo_da_Vinci%2C_from_C2RMF_retouched.jpg"),
    ("great_wave.jpg", "https://upload.wikimedia.org/wikipedia/commons/a/a5/Tsunami_by_hokusai_19th_century.jpg"),
    ("girl_pearl_earring.jpg", "https://upload.wikimedia.org/wikipedia/commons/6/66/Johannes_Vermeer_%281632-1675%29_-_The_Girl_With_The_Pearl_Earring_%281665%29.jpg"),
    ("birth_venus.jpg", "https://upload.wikimedia.org/wikipedia/commons/6/6f/Sandro_Botticelli_-_La_nascita_di_Venere_-_Google_Art_Project.jpg"),
    ("impression_sunrise.jpg", "https://upload.wikimedia.org/wikipedia/commons/5/59/Monet_-_Impression%2C_Sunrise.jpg"),
    ("water_lilies.jpg", "https://upload.wikimedia.org/wikipedia/commons/6/69/Claude_Monet_-_Water_Lilies_-_Google_Art_Project.jpg"),
    ("kiss_klimt.jpg", "https://upload.wikimedia.org/wikipedia/commons/7/7d/Gustav_Klimt_016.jpg"),
    ("van_gogh_self_portrait.jpg", "https://upload.wikimedia.org/wikipedia/commons/b/b2/Vincent_van_Gogh_-_Self-Portrait_-_Google_Art_Project.jpg"),
    ("american_gothic.jpg", "https://upload.wikimedia.org/wikipedia/commons/f/f3/Grant_Wood_-_American_Gothic_-_Google_Art_Project.jpg"),
    ("night_watch.jpg", "https://upload.wikimedia.org/wikipedia/commons/9/94/The_Nightwatch_by_Rembrandt_-_Rijksmuseum.jpg"),
    ("las_meninas.jpg", "https://upload.wikimedia.org/wikipedia/commons/2/28/Diego_Velazquez_Las_Meninas_Detail.jpg"),
    ("sunflowers.jpg", "https://upload.wikimedia.org/wikipedia/commons/4/46/Vincent_van_Gogh_-_Sunflowers_-_VGM_F458.jpg"),
    ("the_scream.jpg", "https://upload.wikimedia.org/wikipedia/commons/f/f4/The_Scream.jpg"),
    ("wanderer_fog.jpg", "https://upload.wikimedia.org/wikipedia/commons/b/b9/Caspar_David_Friedrich_-_Wanderer_above_the_sea_of_fog.jpg"),
    ("sunday_jatte.jpg", "https://upload.wikimedia.org/wikipedia/commons/7/7d/A_Sunday_on_La_Grande_Jatte%2C_Georges_Seurat%2C_1884.jpg"),
    ("hay_wain.jpg", "https://upload.wikimedia.org/wikipedia/commons/3/35/John_Constable_-_The_Hay_Wain.jpg"),
    ("moulin_galette.jpg", "https://upload.wikimedia.org/wikipedia/commons/4/46/Pierre-Auguste_Renoir%2C_Le_Moulin_de_la_Galette.jpg"),
    ("whistlers_mother.jpg", "https://upload.wikimedia.org/wikipedia/commons/1/1b/Whistlers_Mother_high_res.jpg"),
    ("creation_adam.jpg", "https://upload.wikimedia.org/wikipedia/commons/2/22/Michelangelo_-_Creation_of_Adam_%28cropped%29.jpg"),
)


def _limit_long_edge(img: Image.Image, max_side: int = 1600) -> Image.Image:
    w, h = img.size
    if max(w, h) <= max_side:
        return img
    if w >= h:
        nh = max(1, int(round(h * max_side / w)))
        return img.resize((max_side, nh), Image.LANCZOS)
    nw = max(1, int(round(w * max_side / h)))
    return img.resize((nw, max_side), Image.LANCZOS)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener()
    ok = 0
    for name, url in ASSETS:
        dest = OUT / name
        last_err: Exception | None = None
        data = None
        for u in _all_fetch_urls(url):
            req = urllib.request.Request(u, headers={"User-Agent": UA}, method="GET")
            try:
                with opener.open(req, timeout=90) as resp:
                    data = resp.read()
                break
            except Exception as e:
                last_err = e
                data = None
        try:
            if not data:
                raise last_err or RuntimeError("no data")
            _old = int(Image.MAX_IMAGE_PIXELS)
            try:
                Image.MAX_IMAGE_PIXELS = 2_000_000_000
                im = Image.open(io.BytesIO(data)).convert("RGB")
            finally:
                Image.MAX_IMAGE_PIXELS = _old
            im = _limit_long_edge(im, 1600)
            im.save(dest, "JPEG", quality=88, optimize=True)
            print("OK", name, dest.stat().st_size, file=sys.stderr)
            ok += 1
        except Exception as e:
            print("FAIL", name, e, file=sys.stderr)
    print(f"saved {ok}/{len(ASSETS)} -> {OUT}", file=sys.stderr)
    return 0 if ok == len(ASSETS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
