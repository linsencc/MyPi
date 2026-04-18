from __future__ import annotations

import logging
import os
import time

log = logging.getLogger(__name__)


class DisplaySink:
    """Hardware sink: ``show`` must block until the panel refresh completes (e‑ink ~10–30s).

    Swap this class for a device-specific driver on the Pi. For local testing, set
    ``MYPI_EINK_SHOW_DELAY_MS`` to simulate slow refresh.
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
