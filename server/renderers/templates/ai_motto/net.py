"""urllib openers: LLM (optional proxy) vs image CDNs (optional direct)."""

from __future__ import annotations

import os
import urllib.request


def build_llm_proxy_opener(need_proxy: bool = True) -> urllib.request.OpenerDirector:
    if not need_proxy:
        return urllib.request.build_opener()
    proxy = (
        os.environ.get("MYPI_LLM_PROXY", "").strip()
        or os.environ.get("HTTPS_PROXY", "").strip()
        or os.environ.get("https_proxy", "").strip()
    )
    if proxy:
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({"https": proxy, "http": proxy})
        )
    return urllib.request.build_opener()


def build_motto_image_opener() -> urllib.request.OpenerDirector:
    """Image hosts may need a direct route while the LLM still uses MYPI_LLM_PROXY."""
    v = os.environ.get("MYPI_MOTTO_IMAGE_NO_PROXY", "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return urllib.request.build_opener()
    return build_llm_proxy_opener()
