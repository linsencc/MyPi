"""Real Waveshare 13.3″ E6 full-color e-ink display driver.

Requires the Waveshare e-Paper SDK cloned at ``EPD_SDK_PATH``
(default ``/home/linsen/e-Paper/…/python/lib``) and the matching
``DEV_Config_*.so`` in that directory.

Env vars
--------
MYPI_EPD_SDK  – override the path to the ``lib/`` directory containing
                ``epd13in3E.py`` and ``epdconfig.py``.
"""

from __future__ import annotations

import logging
import os
import sys
import threading

from PIL import Image

from display.sink import DisplaySink

log = logging.getLogger(__name__)

_DEFAULT_SDK_LIB = (
    "/home/linsen/workspace/e-Paper/"
    "E-paper_Separate_Program/13.3inch_e-Paper_E/"
    "RaspberryPi/python/lib"
)

EPD_WIDTH = 1200
EPD_HEIGHT = 1600


class EpdE6Sink(DisplaySink):
    """Thread-safe wrapper around the Waveshare EPD 13.3″ E6 driver."""

    def __init__(self) -> None:
        sdk_path = os.environ.get("MYPI_EPD_SDK", _DEFAULT_SDK_LIB)
        if sdk_path not in sys.path:
            sys.path.insert(0, sdk_path)
        try:
            import epd13in3E  # type: ignore[import-untyped]
            self._epd_mod = epd13in3E
        except ImportError as exc:
            raise RuntimeError(
                f"Cannot import epd13in3E from {sdk_path}. "
                "Ensure the Waveshare e-Paper SDK is cloned and "
                "MYPI_EPD_SDK points to the lib/ directory."
            ) from exc

        self._lock = threading.Lock()
        log.info("EpdE6Sink ready (SDK from %s)", sdk_path)

    def show(self, image_path: str) -> None:
        """Render *image_path* (any Pillow-readable format) on the e-ink panel."""
        log.info("EpdE6Sink.show %s", image_path)
        with Image.open(image_path) as raw_img:
            img = raw_img.convert("RGB")

        target_w, target_h = EPD_WIDTH, EPD_HEIGHT
        src_w, src_h = img.size
        if (src_w, src_h) != (target_w, target_h):
            if (src_w, src_h) == (target_h, target_w):
                pass  # driver's getbuffer handles 90° rotation
            else:
                img = img.resize((target_w, target_h), Image.LANCZOS)
                log.info("Resized %dx%d → %dx%d", src_w, src_h, target_w, target_h)

        with self._lock:
            epd = self._epd_mod.EPD()
            try:
                epd.Init()
                buf = epd.getbuffer(img)
                epd.display(buf)
                epd.sleep()
                log.info("EpdE6Sink.show complete")
            except Exception:
                log.exception("EPD display failed")
                try:
                    epd.sleep()
                except Exception:
                    pass
                raise
