"""Web search + LLM to summarize events when Damai yields nothing.

Environment (any one search backend):

- **Bing** v7: ``MYPI_BING_SEARCH_KEY`` or ``MYPI_WEB_SEARCH_KEY`` (treated as Bing key).
  Optional ``MYPI_BING_SEARCH_ENDPOINT`` (default ``https://api.bing.microsoft.com/v7.0/search``).
- **Google Programmable Search**: ``MYPI_GOOGLE_API_KEY`` + ``MYPI_GOOGLE_CSE_ID`` (both required).

Uses ``MYPI_LLM_*`` for the same OpenAI-compatible chat as ``ai_motto`` (see ``llm_events``).
"""

from __future__ import annotations

import json
from datetime import datetime
import logging
import os
import urllib.parse
import urllib.request

from renderers.templates.ai_motto.net import build_llm_proxy_opener

from . import llm_events

log = logging.getLogger(__name__)

_SEARCH_TIMEOUT = 10


def _bing_key() -> str:
    return (
        os.environ.get("MYPI_BING_SEARCH_KEY", "").strip()
        or os.environ.get("MYPI_WEB_SEARCH_KEY", "").strip()
    )


def _google_keys() -> tuple[str, str]:
    return (
        os.environ.get("MYPI_GOOGLE_API_KEY", "").strip(),
        os.environ.get("MYPI_GOOGLE_CSE_ID", "").strip(),
    )


def fetch_search_snippets(query: str, *, max_results: int = 8) -> str:
    """Return concatenated snippets for LLM; empty if no backend configured."""
    q = query.strip()
    if not q:
        return ""

    bing = _bing_key()
    if bing:
        return _bing_snippets(q, bing, max_results=max_results)

    gkey, cx = _google_keys()
    if gkey and cx:
        return _google_cse_snippets(q, gkey, cx, max_results=max_results)

    log.info("weekend_outing: no search API key (Bing or Google CSE), skip search")
    return ""


def _bing_snippets(query: str, key: str, *, max_results: int) -> str:
    endpoint = (
        os.environ.get("MYPI_BING_SEARCH_ENDPOINT", "").strip().rstrip("/")
        or "https://api.bing.microsoft.com/v7.0/search"
    )
    params = urllib.parse.urlencode(
        {"q": query, "count": str(max(1, min(10, max_results))), "mkt": "zh-CN"}
    )
    url = f"{endpoint}?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "Ocp-Apim-Subscription-Key": key,
            "User-Agent": "MyPiWeekendOuting/1.0",
        },
        method="GET",
    )
    opener = build_llm_proxy_opener()
    try:
        with opener.open(req, timeout=_SEARCH_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        log.warning("weekend_outing: Bing search failed: %s", exc)
        return ""

    pages = data.get("webPages") or {}
    items = pages.get("value") or []
    chunks: list[str] = []
    for it in items[:max_results]:
        if not isinstance(it, dict):
            continue
        name = str(it.get("name") or "").strip()
        snip = str(it.get("snippet") or "").strip()
        u = str(it.get("url") or "").strip()
        line = " | ".join(x for x in (name, snip, u) if x)
        if line:
            chunks.append(line)
    return "\n".join(chunks)[:12000]


def _google_cse_snippets(query: str, api_key: str, cx: str, *, max_results: int) -> str:
    params = urllib.parse.urlencode(
        {
            "key": api_key,
            "cx": cx,
            "q": query,
            "num": str(max(1, min(10, max_results))),
            "lr": "lang_zh-CN",
        }
    )
    url = f"https://www.googleapis.com/customsearch/v1?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "MyPiWeekendOuting/1.0"}, method="GET")
    opener = build_llm_proxy_opener()
    try:
        with opener.open(req, timeout=_SEARCH_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        log.warning("weekend_outing: Google CSE failed: %s", exc)
        return ""

    items = data.get("items") or []
    chunks: list[str] = []
    for it in items[:max_results]:
        if not isinstance(it, dict):
            continue
        title = str(it.get("title") or "").strip()
        snip = str(it.get("snippet") or "").strip()
        link = str(it.get("link") or "").strip()
        line = " | ".join(x for x in (title, snip, link) if x)
        if line:
            chunks.append(line)
    return "\n".join(chunks)[:12000]


def build_default_search_query(extra: str) -> str:
    y = datetime.now().year
    base = f"深圳 南山 周末 演唱会 展会 活动 {y}"
    ex = extra.strip()
    if ex:
        return f"{base} {ex}"
    return base


def fetch_events_via_search_llm(
    query: str,
    *,
    max_events: int,
) -> list[str]:
    snippets = fetch_search_snippets(query, max_results=max(5, max_events + 2))
    if not snippets:
        return []
    lines = llm_events.summarize_search_to_event_lines(snippets, max_lines=max_events)
    return lines
