"""Optional single-sentence weekend tip from LLM (weather + events already known)."""

from __future__ import annotations

import json
import logging
import os
import urllib.request

from renderers.templates.ai_motto.llm import assistant_content_from_completion
from renderers.templates.ai_motto.net import build_llm_proxy_opener
from renderers.templates.ai_motto.prompts import (
    DEFAULT_LLM_BASE_URL,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_TIMEOUT,
)

log = logging.getLogger(__name__)


def weekend_tip_one_liner(weather_block: str, events_block: str) -> str | None:
    api_key = os.environ.get("MYPI_LLM_API_KEY", "").strip()
    if not api_key:
        return None
    base_url = os.environ.get("MYPI_LLM_BASE_URL", DEFAULT_LLM_BASE_URL).rstrip("/")
    model = os.environ.get("MYPI_LLM_MODEL", DEFAULT_LLM_MODEL).strip() or DEFAULT_LLM_MODEL
    timeout = int(os.environ.get("MYPI_LLM_TIMEOUT", str(DEFAULT_LLM_TIMEOUT)))

    user = (
        "根据以下已整理信息，用一句中文（40 字以内）给出本周末出行建议，不要重复列出活动名称，不要编造新活动。\n\n"
        f"{weather_block[:2500]}\n\n{events_block[:2500]}"
    )
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "你只输出一句中文建议，不要引号包裹，不要列表。",
                },
                {"role": "user", "content": user},
            ],
            "max_tokens": 120,
            "temperature": 0.5,
        }
    ).encode()

    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/mypi-frame",
            "X-Title": "MyPi Weekend Tip",
        },
        method="POST",
    )
    opener = build_llm_proxy_opener()
    try:
        with opener.open(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        log.info("weekend_outing: weekend tip LLM skipped: %s", exc)
        return None
    text = assistant_content_from_completion(body)
    if not text:
        return None
    one = text.replace("\n", " ").strip()
    if len(one) > 80:
        one = one[:77] + "…"
    return one
