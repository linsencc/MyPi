"""Shenzhen-area events via OpenAI-compatible chat (same ``MYPI_LLM_*`` as 每日寄语 / OpenRouter).

Uses optional ``MYPI_WEEKEND_EVENTS_MODEL`` when set; otherwise ``MYPI_LLM_MODEL``.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.request

from renderers.templates.ai_motto.llm import assistant_content_from_completion
from renderers.templates.ai_motto.net import build_llm_proxy_opener
from renderers.templates.ai_motto.prompts import (
    DEFAULT_LLM_BASE_URL,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_TIMEOUT,
)

log = logging.getLogger(__name__)


def _events_model() -> str:
    alt = os.environ.get("MYPI_WEEKEND_EVENTS_MODEL", "").strip()
    if alt:
        return alt
    return os.environ.get("MYPI_LLM_MODEL", DEFAULT_LLM_MODEL).strip() or DEFAULT_LLM_MODEL


def _system_prompt(max_lines: int) -> str:
    return (
        "你是深圳本地活动信息助理。请根据你的最新检索能力，列出未来几天内在深圳市（含南山、福田等）"
        "可参与的**真实**公众活动：展览、音乐会、戏剧、市集、讲座等。"
        "不得编造具体场馆与日期；不确定则少列。"
        "只输出一个 JSON 对象，键 `lines` 为字符串数组；每条建议格式："
        "「日期或本周｜类型｜短标题」，中文，每条不超过 40 个汉字。"
        f"最多 {max_lines} 条，没有则输出 {{\"lines\":[]}}。"
    )


def _parse_lines_json(raw: str) -> list[str]:
    cleaned = re.sub(r"```json\s*|\s*```", "", raw).strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            arr = data.get("lines")
            if isinstance(arr, list):
                return [str(x).strip() for x in arr if str(x).strip()]
    except json.JSONDecodeError:
        pass
    dec = json.JSONDecoder()
    for i, ch in enumerate(cleaned):
        if ch != "{":
            continue
        try:
            obj, _ = dec.raw_decode(cleaned, i)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            arr = obj.get("lines")
            if isinstance(arr, list):
                return [str(x).strip() for x in arr if str(x).strip()]
    return []


def fetch_shenzhen_event_lines(*, max_lines: int) -> list[str]:
    """Return short event lines; empty if no API key or request fails."""
    api_key = os.environ.get("MYPI_LLM_API_KEY", "").strip()
    if not api_key:
        log.info("weekend_outing: events LLM skipped (MYPI_LLM_API_KEY not set)")
        return []

    base_url = os.environ.get("MYPI_LLM_BASE_URL", DEFAULT_LLM_BASE_URL).rstrip("/")
    model = _events_model()
    timeout = int(os.environ.get("MYPI_LLM_TIMEOUT", str(DEFAULT_LLM_TIMEOUT)))

    user = (
        f"请列出深圳近期最多 {max_lines} 条活动，严格只输出 JSON，例如："
        '{"lines":["周六｜展览｜某某艺术展","…"]}'
    )
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": _system_prompt(max_lines)},
                {"role": "user", "content": user},
            ],
            "max_tokens": 800,
            "temperature": 0.35,
        }
    ).encode()

    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/mypi-frame",
            "X-Title": "MyPi Weekend Events",
        },
        method="POST",
    )
    opener = build_llm_proxy_opener()
    try:
        with opener.open(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        log.warning("weekend_outing: events LLM request failed: %s", exc)
        return []

    raw = assistant_content_from_completion(body)
    if not raw:
        return []
    lines = _parse_lines_json(raw)
    return lines[:max_lines] if lines else []
