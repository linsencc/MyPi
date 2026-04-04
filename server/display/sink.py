from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class DisplaySink:
    """Mock hardware sink: logs path. Swap for E6 driver later."""

    def show(self, image_path: str) -> None:
        log.info("DisplaySink.show %s", image_path)
