from __future__ import annotations

import logging
import os
import time

log = logging.getLogger(__name__)


class DisplaySink:
    """Hardware sink: ``show`` must block until the panel refresh completes (e‑ink ~10–30s).

    For local testing, set ``MYPI_EINK_SHOW_DELAY_MS`` to simulate slow refresh.
    On the Pi, set ``MYPI_DISPLAY=epd_e6`` to use the real Waveshare driver.
    """

    def show(self, image_path: str) -> None:
        log.info("DisplaySink.show %s", image_path)
        raw = os.environ.get("MYPI_EINK_SHOW_DELAY_MS", "").strip()
        if raw:
            try:
                ms = int(raw, 10)
            except ValueError:
                ms = 0
            else:
                if ms > 0:
                    time.sleep(ms / 1000.0)


def create_display_sink() -> DisplaySink:
    """Return the real EPD sink or a mock based on ``MYPI_DISPLAY`` env var.

    * ``epd_e6`` → :class:`~display.epd_e6_sink.EpdE6Sink`
    * anything else (default) → :class:`DisplaySink` (mock / delay-only)
    """
    mode = os.environ.get("MYPI_DISPLAY", "mock").strip().lower()
    if mode == "epd_e6":
        from display.epd_e6_sink import EpdE6Sink
        return EpdE6Sink()
    log.info("Using mock DisplaySink (set MYPI_DISPLAY=epd_e6 for real hardware)")
    return DisplaySink()
