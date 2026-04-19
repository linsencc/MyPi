"""Apply `frameTuning.imageSettings` before save + e-ink display.

Must stay in sync with `web/src/data/frame-config.ts` `getPreviewImageFilter`:
same clamps and composite factors (brightness → contrast boost → color/sat).

The browser previously simulated ink with CSS only; the PNG was raw. We now bake
tuning into the saved image so `/api/v1/output/...` matches the panel, and the
hero preview skips duplicate CSS filters for those URLs.
"""

from __future__ import annotations

import logging
from typing import Any

from PIL import Image, ImageEnhance

log = logging.getLogger(__name__)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _float(settings: dict[str, Any], key: str, default: float) -> float:
    v = settings.get(key, default)
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def apply_frame_tuning(img: Image.Image, frame_tuning: dict[str, Any] | None) -> Image.Image:
    """PIL chain mirroring `getPreviewImageFilter` (no second sharpness pass)."""
    if not frame_tuning:
        return img
    raw = frame_tuning.get("imageSettings")
    if not isinstance(raw, dict):
        return img

    b = _clamp(_float(raw, "brightness", 1.0), 0.2, 2.5)
    c = _clamp(_float(raw, "contrast", 1.0), 0.2, 2.5)
    col = _clamp(_float(raw, "saturation", 1.0), 0.0, 3.0)
    ink = _clamp(_float(raw, "inky_saturation", 0.5), 0.0, 1.0)
    sharp = _clamp(_float(raw, "sharpness", 1.0), 0.0, 2.0)

    contrast_boost = c * (1 + max(0.0, sharp - 1.0) * 0.15) * (0.88 + ink * 0.28)
    sat = max(0.55, col * (0.75 + ink * 0.5))

    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    elif img.mode == "L":
        img = img.convert("RGB")

    img = ImageEnhance.Brightness(img).enhance(b)
    img = ImageEnhance.Contrast(img).enhance(contrast_boost)
    img = ImageEnhance.Color(img).enhance(sat)
    return img
