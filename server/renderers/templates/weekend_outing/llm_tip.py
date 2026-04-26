"""出行建议：围绕活动的短导语；一般不提天气（除非高风险摘要允许）。"""

from __future__ import annotations

import html
import json
import logging
import os
import re
import urllib.request
from typing import Any

from renderers.templates.ai_motto.llm import assistant_content_from_completion
from renderers.templates.ai_motto.net import build_llm_proxy_opener
from renderers.templates.ai_motto.prompts import (
    DEFAULT_LLM_BASE_URL,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_TIMEOUT,
)

log = logging.getLogger(__name__)

# 约 4～5 行（随参考稿字号），硬上限避免被裁切（原 88 字约 1.7 倍）
ADVICE_LEAD_MAX_CHARS = 150

_BULLET_DATE = re.compile(
    r"^(\d{1,2}/\d{1,2}\s*周[一二三四五六日天])\s*([：:])\s*(.*)$"
)


def clamp_advice_lead(text: str | None, max_chars: int = ADVICE_LEAD_MAX_CHARS) -> str:
    """截断为短导语，末尾省略号。"""
    t = (text or "").replace("\n", " ").strip()
    if len(t) <= max_chars:
        return t
    return t[: max(1, max_chars - 1)] + "…"


def weekend_tip_one_liner(weather_block: str, events_block: str) -> str | None:
    """兼容旧调用（``weather_block`` 视为风险摘要，可传空）。"""
    block = weekend_advice_block(weather_block, events_block, area_label="", date_range_label="")
    if not block:
        return None
    return clamp_advice_lead(block.get("lead")) or None


def weekend_advice_block(
    weather_risk_hint: str,
    events_block: str,
    *,
    area_label: str,
    date_range_label: str,
) -> dict[str, Any] | None:
    """请求 LLM 输出短 JSON：``{"lead":"…"}``（忽略 bullets）。

    ``weather_risk_hint`` 为空时，禁止在 lead 中讨论一般天气、雨具、穿衣、市内交通；
    非空时仅按其中允许的范围点到为止提及天气与安全。
    """
    api_key = os.environ.get("MYPI_LLM_API_KEY", "").strip()
    if not api_key:
        return None
    base_url = os.environ.get("MYPI_LLM_BASE_URL", DEFAULT_LLM_BASE_URL).rstrip("/")
    model = os.environ.get("MYPI_LLM_MODEL", DEFAULT_LLM_MODEL).strip() or DEFAULT_LLM_MODEL
    timeout = int(os.environ.get("MYPI_LLM_TIMEOUT", str(DEFAULT_LLM_TIMEOUT)))

    meta = f"地区：{area_label or '本地'}。日期参考：{date_range_label or '未给出'}。"
    risk = (weather_risk_hint or "").strip()
    if risk:
        wx_block = f"---天气对活动的影响（仅允许在必要时引用，勿复述晴雨温度细节）---\n{risk[:900]}"
    else:
        wx_block = (
            "---天气---\n"
            "（上方页面「天气」区已展示预报；本段禁止在 lead 中写一般天气、雨具、穿衣、市内交通或路程串联。）"
        )
    user = (
        "根据以下活动列表（每条含时间、类型、标题、地址），输出**严格 JSON 对象**，"
        "不要 markdown 代码围栏，不要其它文字。\n"
        '格式：{"lead":"一段中文"}\n'
        "要求：\n"
        f"1) 仅一个键 lead；字符串总长 **{ADVICE_LEAD_MAX_CHARS} 字以内**（约四五句以内），一句写完，禁止换行、禁止分点列表。\n"
        "2) 重点写：如何按日期/区域安排所列活动（顺序、同区合并、转场时间、开放与订票提示等）；"
        "可用顿号、分号连接，勿展开长叙述。\n"
        "3) 勿编造列表中没有的活动名或场馆。\n"
        "4) 若「天气对活动的影响」小节给出了风险提示，才可用一两句呼应；否则完全不要写天气或出行方式。\n"
        f"{meta}\n\n{wx_block}\n\n---活动---\n{events_block[:3200]}"
    )
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你只输出合法 JSON 对象，仅含键 lead（字符串）。禁止 bullets、禁止数组根、禁止注释。"
                        "除非用户明确提供「天气对活动的影响」且有必要，否则 lead 中不要写雨具、气温、晴雨、地铁公交等。"
                    ),
                },
                {"role": "user", "content": user},
            ],
            "max_tokens": 400,
            "temperature": 0.3,
        }
    ).encode()

    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/mypi-frame",
            "X-Title": "MyPi Weekend Advice",
        },
        method="POST",
    )
    opener = build_llm_proxy_opener()
    try:
        with opener.open(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        log.info("weekend_outing: advice LLM skipped: %s", exc)
        return None
    text = assistant_content_from_completion(body)
    if not text:
        return None
    cleaned = re.sub(r"```json\s*|\s*```", "", text).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        dec = json.JSONDecoder()
        data = None
        for i, ch in enumerate(cleaned):
            if ch != "{":
                continue
            try:
                obj, _ = dec.raw_decode(cleaned, i)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and "lead" in obj:
                data = obj
                break
        if not isinstance(data, dict):
            return None
    if not isinstance(data, dict):
        return None
    lead = clamp_advice_lead(str(data.get("lead") or "").strip())
    if not lead:
        return None
    return {"lead": lead, "bullets": []}


def format_advice_bullet_html(line: str) -> str:
    """分日要点（当前建议区已不用，保留供其它模板）。"""
    t = (line or "").strip()
    if not t:
        return ""
    m = _BULLET_DATE.match(t)
    if m:
        head = html.escape(m.group(1))
        sep = m.group(2)
        rest = html.escape(m.group(3))
        return f"<strong>{head}</strong>{sep}{rest}"
    return html.escape(t)


def advice_fallback_from_rule(*, has_events: bool, risk_suffix: str = "") -> dict[str, Any]:
    """无 LLM：活动向导语，可选极短天气风险提示后缀。"""
    if has_events:
        lead = "按列表日期与地点，可优先安排同区场次以减少折返；开场前核对场馆开放、闭馆日与票务渠道。"
    else:
        lead = "可到各馆官网或票务平台查询近期展览、演出及开票信息。"
    suf = (risk_suffix or "").strip()
    if suf:
        lead = f"{lead}{suf}"
    return {"lead": clamp_advice_lead(lead), "bullets": []}
