"""LLM: condense web search snippets into short event lines (no web by itself)."""

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

def _system_prompt(max_lines: int) -> str:
    return (
        "你是助理，只根据用户提供的「网页搜索摘要」整理活动信息。"
        "不得编造摘要里未出现的具体演出名称或日期。"
        "输出严格为 JSON 对象，键 lines 为字符串数组；每条格式：日期或待定｜类型｜短标题，中文。"
        "每条总长不超过 40 个汉字，便于电子纸一行显示。"
        f"最多 {max_lines} 条，不足则少输出。"
    )


def summarize_search_to_event_lines(snippets: str, *, max_lines: int) -> list[str]:
    api_key = os.environ.get("MYPI_LLM_API_KEY", "").strip()
    if not api_key or not snippets.strip():
        return _fallback_lines_from_snippets(snippets, max_lines)

    base_url = os.environ.get("MYPI_LLM_BASE_URL", DEFAULT_LLM_BASE_URL).rstrip("/")
    model = os.environ.get("MYPI_LLM_MODEL", DEFAULT_LLM_MODEL).strip() or DEFAULT_LLM_MODEL
    timeout = int(os.environ.get("MYPI_LLM_TIMEOUT", str(DEFAULT_LLM_TIMEOUT)))

    user = (
        f"最多整理 {max_lines} 条。搜索摘要如下：\n\n"
        f"{snippets[:10000]}\n\n"
        '只输出 JSON，例如：{"lines":["…","…"]}'
    )
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": _system_prompt(max_lines)},
                {"role": "user", "content": user},
            ],
            "max_tokens": 500,
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
            "X-Title": "MyPi Weekend Outing",
        },
        method="POST",
    )
    opener = build_llm_proxy_opener()
    try:
        with opener.open(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        log.warning("weekend_outing: LLM events summarize failed: %s", exc)
        return _fallback_lines_from_snippets(snippets, max_lines)

    raw = assistant_content_from_completion(body)
    lines = _parse_lines_json(raw)
    if lines:
        return lines[:max_lines]
    return _fallback_lines_from_snippets(snippets, max_lines)


def _parse_lines_json(raw: str) -> list[str]:
    cleaned = re.sub(r"```json\s*|\s*```", "", raw).strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            arr = data.get("lines")
            if isinstance(arr, list):
                out = [str(x).strip() for x in arr if str(x).strip()]
                return out
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


def _fallback_lines_from_snippets(snippets: str, max_lines: int) -> list[str]:
    """First lines of snippets as ultra-weak fallback."""
    out: list[str] = []
    for ln in snippets.splitlines():
        t = ln.strip()
        if len(t) > 12 and "|" in t:
            out.append(t[:120])
        if len(out) >= max_lines:
            break
    return out
