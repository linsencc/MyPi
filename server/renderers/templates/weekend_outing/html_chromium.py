"""周末出行专用：把 HTML 字符串经本机 Chromium 无头截图转成 PIL 图。

与 InkyPi 思路一致（临时文件 + ``chromium --headless --screenshot``）。
需安装 ``chromium`` / ``chromium-headless-shell`` / ``chrome`` 之一并在 ``PATH`` 中，
或设置 ``MYPI_CHROMIUM_BIN`` 指向可执行文件。
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

log = logging.getLogger(__name__)

_DEFAULT_SHOT_TIMEOUT_S = 90.0


# Headless screenshot: PATH 可能极短（systemd/gunicorn）；再试常见绝对路径（含 Raspberry Pi OS）。
_FALLBACK_CHROMIUM_PATHS: tuple[Path, ...] = (
    Path("/usr/bin/chromium"),
    Path("/usr/bin/chromium-browser"),
    Path("/snap/bin/chromium"),
)


def _find_chromium_binary() -> str | None:
    env = os.environ.get("MYPI_CHROMIUM_BIN", "").strip()
    if env:
        if Path(env).is_file():
            return env
        log.warning("MYPI_CHROMIUM_BIN is set but not a regular file (ignored): %s", env)
    for candidate in (
        "chromium-headless-shell",
        "chromium",
        "google-chrome",
        "chrome",
    ):
        path = shutil.which(candidate)
        if path:
            return path
    for p in _FALLBACK_CHROMIUM_PATHS:
        if p.is_file():
            return str(p)
    return None


def render_html_to_image(
    html: str,
    size: tuple[int, int],
    *,
    timeout_s: float | None = None,
) -> Image.Image:
    """Write ``html`` to a temp file, run headless Chromium screenshot, return RGB image."""
    w, h = int(size[0]), int(size[1])
    if w < 32 or h < 32:
        raise ValueError("render_html_to_image: dimensions too small")

    browser = _find_chromium_binary()
    if not browser:
        raise RuntimeError(
            "No Chromium-based browser found. Install chromium or chromium-headless-shell, "
            "or set MYPI_CHROMIUM_BIN to the executable."
        )

    t_out = float(timeout_s) if timeout_s is not None else _DEFAULT_SHOT_TIMEOUT_S

    html_path: str | None = None
    png_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".html", delete=False, mode="w", encoding="utf-8"
        ) as hf:
            hf.write(html)
            html_path = hf.name

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as pf:
            png_path = pf.name

        # Windows: file URL for local path
        uri = Path(html_path).resolve().as_uri()

        cmd = [
            browser,
            uri,
            "--headless",
            f"--screenshot={png_path}",
            f"--window-size={w},{h}",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--hide-scrollbars",
            "--mute-audio",
            "--no-sandbox",
            "--disable-extensions",
            # 避免 file:// 页面仍去拉外网子资源时在弱网/离线设备上卡死直至超时
            "--disable-background-networking",
        ]
        # Older chromium may not support --headless=new; try without if needed in future.

        log.debug("html_chromium: running screenshot cmd=%s", cmd[:4])
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=t_out,
            check=False,
        )
        if proc.returncode != 0:
            err = (proc.stderr or b"").decode("utf-8", errors="replace")[:2000]
            raise RuntimeError(
                f"Chromium screenshot failed (code={proc.returncode}): {err or 'no stderr'}"
            )
        if not Path(png_path).is_file():
            raise RuntimeError("Chromium did not write screenshot PNG")

        with Image.open(png_path) as img:
            out = img.convert("RGB").copy()
        if out.size != (w, h):
            out = out.resize((w, h), Image.LANCZOS)
        return out
    finally:
        for p in (html_path, png_path):
            if p:
                try:
                    Path(p).unlink(missing_ok=True)
                except OSError:
                    pass
