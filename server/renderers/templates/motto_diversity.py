"""Stratified sources + recent-quote memory for ai_motto LLM diversity.

Avoids single-film bans: each request picks a **mutually exclusive content stratum** so the model
cannot default to the same few “global classic” quotes. Recent outputs are persisted and injected
into the prompt to reduce near-duplicates across renders.
"""

from __future__ import annotations

import json
import logging
import random
import re
import time
from dataclasses import dataclass

from storage.paths import recent_ai_mottos_path

log = logging.getLogger(__name__)

_RECENT_FILE_MAX_LINES = 48
_RECENT_PROMPT_MAX = 14


@dataclass(frozen=True)
class MottoStratum:
    """One exclusive topic for this request; model must stay inside it."""

    key: str
    instruction: str


# 每次随机一层：影视类按地域/载体拆开，避免落到「英语大片励志台词」这一统计默认。
_MOTTO_FORMAT_HINT = (
    " 输出句式严格为 「正文摘录」 -- 出处（出处：影视写《片名》，其它写作者/书名/人名）；"
    "正文宜短、洗练，整段含符号不超过 34 字。"
)
MOTTO_STRATA: tuple[MottoStratum, ...] = (
    MottoStratum(
        "zh_lit",
        "【本次唯一维度·中国文学】仅选：中国名著或现当代作家短摘/原话，可带简称书名。**禁止**外国文学、影视、翻译腔口号。"
        + _MOTTO_FORMAT_HINT,
    ),
    MottoStratum(
        "world_lit",
        "【本次唯一维度·外国文学】仅选：外国文学**汉译**摘句，可带译者或简称书名。**禁止**影视台词与中文原创作品。"
        + _MOTTO_FORMAT_HINT,
    ),
    MottoStratum(
        "poetry",
        "【本次唯一维度·诗词古文】仅选：古诗词、骈文或文言短章一句，可带作者。**禁止**白话影视与近现代口号。"
        + _MOTTO_FORMAT_HINT,
    ),
    MottoStratum(
        "figures",
        "【本次唯一维度·人物语录】仅选：历史人物、思想家、科学家等**可核对的**短语录，须带人名。**禁止**虚构影视对白。"
        + _MOTTO_FORMAT_HINT,
    ),
    MottoStratum(
        "essay",
        "【本次唯一维度·杂文随笔】仅选：近现代杂文、随笔、书评中的句子，带作者。**禁止**影视。"
        + _MOTTO_FORMAT_HINT,
    ),
    MottoStratum(
        "film_huayu",
        "【本次唯一维度·影视·华语】仅选：华语（含港台）影视作品台词；**出处须为《片名》。** **禁止**非华语片。"
        + _MOTTO_FORMAT_HINT,
    ),
    MottoStratum(
        "film_jp_kr",
        "【本次唯一维度·影视·日韩】仅选：日本或韩国**真人影视**台词；**出处须为《片名》。** **禁止**华语、好莱坞、动画长片（本片种为真人）。"
        + _MOTTO_FORMAT_HINT,
    ),
    MottoStratum(
        "film_europe_row",
        "【本次唯一维度·影视·欧陆与其它】仅选：欧洲各国、英国、拉美、中东、印度等**非美国好莱坞主流商业片**台词；**出处须为《片名》。** **禁止**美国英语励志大片套路。"
        + _MOTTO_FORMAT_HINT,
    ),
    MottoStratum(
        "film_animation_doc",
        "【本次唯一维度·影视·动画/纪录】仅选：**动画电影**或**纪录电影**台词；**出处须为《片名》。** **禁止**真人英语商业大片。"
        + _MOTTO_FORMAT_HINT,
    ),
)


RETRY_DIVERSIFY_SUFFIX = (
    "【重试要求】上一稿与「近期去重」过于相近，或未遵守【本次唯一维度】。"
    "请**彻底换题**（换作品、作者、时代、语种）；禁止同句改标点、禁止只换一两个词。"
    "motto 仍须严格为 「正文」 -- 出处（直角引号 + 空格 + -- + 空格 + 出处）。"
)


def pick_motto_stratum() -> MottoStratum:
    return random.Random(time.time_ns()).choice(MOTTO_STRATA)


def _norm(s: str) -> str:
    s = re.sub(r"\s+", "", s)
    return s.strip()


def load_recent_mottos() -> list[str]:
    p = recent_ai_mottos_path()
    if not p.is_file():
        return []
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as e:
        log.warning("motto_diversity: read recent file failed: %s", e)
        return []
    out: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
            m = str(o.get("m", "")).strip()
        except json.JSONDecodeError:
            m = line[:400]
        if m:
            out.append(m)
    return out[-_RECENT_PROMPT_MAX:]


def append_motto_to_recent(motto: str) -> None:
    motto = motto.replace("\n", " ").strip()[:600]
    if not motto:
        return
    p = recent_ai_mottos_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = {"t": time.time(), "m": motto}
    try:
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError as e:
        log.warning("motto_diversity: append recent failed: %s", e)
        return
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    if len(lines) > _RECENT_FILE_MAX_LINES:
        try:
            p.write_text("\n".join(lines[-_RECENT_FILE_MAX_LINES:]) + "\n", encoding="utf-8")
        except OSError as e:
            log.warning("motto_diversity: trim recent file failed: %s", e)


def format_recent_block(recent: list[str]) -> str:
    if not recent:
        return "【近期去重】尚无历史记录；请按本次维度自由选题。"
    body = "\n".join(f"- {t}" for t in recent[-_RECENT_PROMPT_MAX:])
    return (
        "【近期去重】下列为此前已展示过的寄语（勿逐字复述，勿仅改一两字）：\n"
        f"{body}"
    )


def is_motto_too_similar(motto: str, recent: list[str]) -> bool:
    """Heuristic overlap with recent lines (prefix / containment)."""
    m = _norm(motto)
    if len(m) < 10:
        return False
    for r in recent:
        r2 = _norm(r)
        if not r2 or len(r2) < 10:
            continue
        if m == r2:
            return True
        n = min(len(m), len(r2), 26)
        if n >= 14 and m[:n] == r2[:n]:
            return True
        shorter, longer = (m, r2) if len(m) <= len(r2) else (r2, m)
        if len(shorter) >= 14 and shorter in longer:
            return True
    return False
