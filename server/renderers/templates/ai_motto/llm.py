"""OpenAI-compatible chat completion for motto + image_prompt."""

from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request

from .diversity import (
    RETRY_DIVERSIFY_SUFFIX,
    append_motto_to_recent,
    format_recent_block,
    is_motto_too_similar,
    load_recent_mottos,
    pick_motto_stratum,
)
from .net import build_llm_proxy_opener
from .prompts import (
    DEFAULT_LLM_BASE_URL,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_TIMEOUT,
    SYSTEM_PROMPT,
    USER_PROMPT,
    fallback_motto_for_day,
)

log = logging.getLogger(__name__)


def strip_thinking_blocks(text: str) -> str | None:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    lines = text.splitlines()
    cjk_lines = [l for l in lines if re.search(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]", l)]
    result = "\n".join(cjk_lines).strip()
    return result if result else None


def parse_llm_json_blob(raw: str) -> dict | None:
    """Parse JSON object from model output; tolerate fences and leading/trailing text."""
    cleaned = re.sub(r"```json\s*|\s*```", "", raw).strip()
    try:
        data = json.loads(cleaned)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    dec = json.JSONDecoder()
    for i, ch in enumerate(cleaned):
        if ch != "{":
            continue
        try:
            obj, _end = dec.raw_decode(cleaned, i)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and any(
            k in obj for k in ("motto", "image_prompt", "imagePrompt")
        ):
            return obj
    return None


def image_prompt_from_data(data: dict) -> str | None:
    v = data.get("image_prompt")
    if v is None or (isinstance(v, str) and not v.strip()):
        v = data.get("imagePrompt")
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def assistant_content_from_completion(body: object) -> str:
    """OpenAI-style chat completion message content (string or multimodal list)."""
    if not isinstance(body, dict):
        return ""
    try:
        choices = body["choices"]
        msg = choices[0]["message"]
    except (KeyError, IndexError, TypeError):
        return ""
    if not isinstance(msg, dict):
        return ""
    c = msg.get("content")
    if isinstance(c, str):
        return c.strip()
    if isinstance(c, list):
        parts: list[str] = []
        for item in c:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    t = item.get("text")
                    if isinstance(t, str):
                        parts.append(t)
                elif isinstance(item.get("text"), str):
                    parts.append(str(item["text"]))
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts).strip()
    return ""


def call_llm_for_motto() -> tuple[str, str | None]:
    """Returns (motto, image_prompt). image_prompt may be None."""
    api_key = os.environ.get("MYPI_LLM_API_KEY", "").strip()
    if not api_key:
        log.info("ai_motto: MYPI_LLM_API_KEY not set, motto fallback and no image")
        return fallback_motto_for_day(), None

    base_url = os.environ.get("MYPI_LLM_BASE_URL", DEFAULT_LLM_BASE_URL).rstrip("/")
    model = os.environ.get("MYPI_LLM_MODEL", DEFAULT_LLM_MODEL).strip() or DEFAULT_LLM_MODEL
    timeout = int(os.environ.get("MYPI_LLM_TIMEOUT", str(DEFAULT_LLM_TIMEOUT)))

    recent = load_recent_mottos()
    stratum = pick_motto_stratum()
    log.info("ai_motto: stratum=%s recent_lines=%s", stratum.key, len(recent))
    base_user = f"{USER_PROMPT}\n\n{stratum.instruction}\n\n{format_recent_block(recent)}"
    opener = build_llm_proxy_opener()

    motto = ""
    image_prompt: str | None = None
    raw = ""

    for attempt in range(3):
        user_content = base_user if attempt == 0 else f"{base_user}\n\n{RETRY_DIVERSIFY_SUFFIX}"
        payload = json.dumps({
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": 520,
            "temperature": 0.92,
        }).encode()

        req = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://github.com/mypi-frame",
                "X-Title": "MyPi Digital Frame",
            },
            method="POST",
        )

        try:
            with opener.open(req, timeout=timeout) as resp:
                body = json.loads(resp.read())
            raw = assistant_content_from_completion(body)
            if not raw:
                log.warning(
                    "ai_motto: LLM empty assistant content (attempt %s)",
                    attempt + 1,
                )
                if attempt < 2:
                    continue
                return fallback_motto_for_day(), None
            log.info("ai_motto: LLM attempt %s raw %d chars", attempt + 1, len(raw))

            data = parse_llm_json_blob(raw)
            if not data:
                log.warning(
                    "ai_motto: LLM response is not valid JSON (attempt %s)",
                    attempt + 1,
                )
                if attempt < 2:
                    continue
                text = strip_thinking_blocks(raw)
                return text or fallback_motto_for_day(), None

            motto = (data.get("motto") or "").strip()
            image_prompt = image_prompt_from_data(data)
            if not motto:
                motto = strip_thinking_blocks(raw) or fallback_motto_for_day()
            if motto and not image_prompt:
                log.info("ai_motto: LLM returned motto but empty image_prompt; text-only layout")

            if motto and not is_motto_too_similar(motto, recent):
                append_motto_to_recent(motto)
                return motto, image_prompt

            if attempt < 2:
                log.warning(
                    "ai_motto: motto too similar to recent or weak diversity, retrying (%s/2)",
                    attempt + 1,
                )
                continue
            log.warning("ai_motto: still similar after retries; using last motto")
            append_motto_to_recent(motto)
            return motto, image_prompt
        except urllib.error.HTTPError as exc:
            err_body = ""
            try:
                err_body = exc.read().decode("utf-8", errors="replace")[:600]
            except Exception:
                pass
            log.warning(
                "ai_motto: LLM HTTP %s body_prefix=%r",
                exc.code,
                err_body[:400],
            )
            if attempt < 2 and exc.code in (408, 425, 429, 500, 502, 503, 504):
                time.sleep(0.8 * (attempt + 1))
                continue
            return fallback_motto_for_day(), None
        except json.JSONDecodeError as exc:
            log.warning("ai_motto: LLM response not JSON (attempt %s): %s", attempt + 1, exc)
            if attempt < 2:
                continue
            return fallback_motto_for_day(), None
        except Exception as exc:
            log.warning("ai_motto: LLM call failed (attempt %s): %s", attempt + 1, exc)
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
                continue
            return fallback_motto_for_day(), None

    return motto or fallback_motto_for_day(), image_prompt
