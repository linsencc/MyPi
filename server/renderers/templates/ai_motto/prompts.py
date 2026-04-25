"""LLM prompts and offline fallbacks for 每日寄语 (motto vs wallpaper image_prompt are independent)."""

from __future__ import annotations

import random
import textwrap
from datetime import datetime

# Defaults for callers (env overrides in llm.py).
DEFAULT_LLM_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_LLM_MODEL = "deepseek/deepseek-chat"
DEFAULT_LLM_TIMEOUT = 20

# Style moodboard (human-curated wallpaper pins); image_prompt LLM is steered to match this vibe, not to match the Chinese motto.
# https://www.pinterest.com/elliotprl/wallpaper/_tools/organize/?organization_feed=False

# 整行 motto（含「」、空格、--、出处）字符上限；与排版 max_lines 一并调整。
MOTTO_MAX_CHARS = 96

SYSTEM_PROMPT = textwrap.dedent(f"""\
    你是「每日寄语」**文案**生成器：只输出**一个合法 JSON 对象**（UTF-8），**仅含键 `motto`**。禁止 Markdown 代码围栏、禁止 JSON 前后的说明或标签。

    ## 输出形状
    {{"motto":"……"}}
    （合法 JSON：键与字符串用英文双引号；字符串内若含英文双引号须用反斜杠转义。motto 正文通常无需英文双引号。）

    ## motto（**简体中文**正文 + 出处，硬性版式）
    1. **语言**：`motto` **整句须为简体中文书面语**（汉字为主，含常用中文标点）；`「…」` 内为中文摘句或通顺的**中文译文**；`--` 后出处用中文习惯写法。**禁止**出现日文**平假名・片假名**（ひらがな/カタカナ）、韩文**谚文**、俄文西里尔字母、整段拉丁字母正文；影视对白即使是日韩片也**只输出中译台词**，不得保留原文假名。
    2. 整行唯一格式：`「正文摘录」 -- 出处`（无换行、无第二句）
    3. 引号：仅用中文直角引号 「 与 」；不要用半角 " 或弯引号
    4. 分隔：正文结束符 `」` 之后 **一个半角空格 + 两个 ASCII 减号 -- + 一个半角空格** 再接出处；**禁止**用破折号 — / —— 代替 `--`
    5. 出处：文学可写书名或作者；影视须 `《片名》`（片名可保留少量外文专名用字，仍以中文语境为主）；诗词古文写作者；人物语录写人名（可加朝代/国别简称）
    6. 长度：从首字「到出处末字，**总长 ≤ {MOTTO_MAX_CHARS} 个字符**（计空格与标点）
    7. 内容：真实作品或公认可核对的摘句；**正文宜有信息量**，但仍洗练，忌口号堆砌；汉译外文读起来要像中文书面语
    8. 忌空洞套话（少用「愿你」「不负韶华」「加油」之类叠用）；不写日期、不写称呼语

    ## 与用户消息的配合（必须同时满足）
    - 【本次唯一维度】：选题**只能**落在该维度内，不得跨界（例如指定诗词则不得输出影视台词）。
    - 【近期去重】：新句须在**作品/立意/措辞**上与列表中任一条明显不同；禁止只改标点或替换一两个词。
    - 避免总选模型最常见的几条「全球通用品」；略冷门但贴切优于大路货。

    ## 版式核对（生成前自检）
    输出前确认：行首为 「、行末为出处；中间为 `空格--空格`；总长 ≤{MOTTO_MAX_CHARS}；**全句可读作中文**；除 `motto` 外不要输出其它键。
""")

MOTTO_CHINESE_ENFORCEMENT = textwrap.dedent("""\
    【中文纠偏】上一稿 **不是合格的中文寄语**：须输出**简体中文**整句，`「…」` 内为中文或通顺中译；`--` 后为中文出处习惯。
    **禁止**日文假名（平假名・片假名，含半角カナ）、韩文谚文、非中文主体；日韩影视须**仅中文译本**台词。仍须满足系统提示中的版式与字数。
""")

USER_PROMPT = textwrap.dedent(f"""\
    请按**用户消息中本轮的【本次唯一维度】与【近期去重】**生成一条新的**简体中文**寄语（不要英文/日文假名/韩文作主句或混写）。

    - motto：严格使用 `「正文」 -- 出处` 版式；正文可充分展开，**整行 ≤ {MOTTO_MAX_CHARS} 字符**；真实摘句、忌空泛鸡汤。
""")

SYSTEM_PROMPT_WALLPAPER = textwrap.dedent("""\
    你是「全屏插画壁纸」英文检索词生成器，与任何中文寄语**无关**；只输出**一个合法 JSON**（UTF-8），**仅含键 `image_prompt`**。禁止 Markdown 围栏、禁止 JSON 外说明。

    ## 输出形状
    {"image_prompt":"……"}

    ## 风格目标（对齐 Pinterest 画板「wallpaper」类精选：动漫风景壁纸、概念场景、治愈系自然）
    参考气质：anime scenery wallpaper、scenery / landscape concept art、watercolor 或 painterly 插画、柔和光线、开阔远景；可出现荷塘与小舟、绿荫树冠、草坡野花、海边崖岸、田园小屋、云层天光等，偏 Ghibli 式宁静或 laptop aesthetic 插画壁纸。**不要**为了「配合某句中文」而选题——每次自由换场景与光色。

    ## image_prompt（英文）
    - **50–75 个英文词**；以**可画面化的名词与场景**开头，再接画风词；少用冗长从句与 and/with/that 串成一整句。
    - 全彩、偏插画或壁纸感、竖屏友好或易竖裁的宽幅远景。
    - 可用词簇示例（按需组合，勿机械堆砌）：anime landscape illustration, aesthetic wallpaper, soft golden light, vivid greens, dreamy atmosphere, cozy countryside, distant mountains, lotus pond, tree canopy, coastal cliff, watercolor, painterly.
    - **禁止**：黑白 / sepia、室内为主、新闻街拍、**人脸或人像为主体**（至多远处不可辨小点）、画面内文字或水印、画框。

    ## 自检
    仅 `image_prompt` 键；英文；50–75 词；无人像主体。
""")

USER_PROMPT_WALLPAPER = textwrap.dedent("""\
    请生成**一条**新的英文 `image_prompt`（与寄语文案无关）。自由选题：自然或幻想风景、光色与构图每次尽量与常见默认不同。
""")

_FALLBACK_MESSAGES = (
    "「人生如逆旅，我亦是行人。」 -- 苏轼",
    "「世上只有一种英雄主义，就是在认清生活真相之后依然热爱生活。」 -- 罗曼·罗兰",
    "「一个人知道自己为什么而活，就可以忍受任何一种生活。」 -- 尼采",
    "「我来到这个世界上，为了看看太阳和蓝色的地平线。」 -- 巴尔蒙特",
    "「路漫漫其修远兮，吾将上下而求索。」 -- 屈原",
    "「生活不可能像你想象得那么好，但也不会像你想象得那么糟。」 -- 莫泊桑",
)

# Offline / LLM-fail: English scene blurbs for Pinscrape (wallpaper-board vibe, independent of motto).
_FALLBACK_WALLPAPER_PROMPTS: tuple[str, ...] = (
    "anime scenery wallpaper rolling green hills wildflowers watercolor painterly soft golden afternoon light distant cottage aesthetic landscape illustration dreamy vivid colors",
    "lotus pond wooden boat lily pads calm green water illustration style peaceful nature wallpaper aesthetic vertical friendly soft light painterly anime landscape",
    "coastal cliff ocean grass wildflowers anime landscape illustration golden hour aesthetic wallpaper painterly distant waves dreamy pastel sky wide vista",
    "tree canopy looking up lush green leaves dappled sunlight forest path anime scenery wallpaper watercolor mood peaceful aesthetic illustration laptop wallpaper",
    "village rooftops distant mountains morning mist watercolor anime landscape aesthetic wallpaper cozy countryside soft light painterly dreamy wide composition",
)


def fallback_motto_for_day() -> str:
    """Rotate through canned quotes when LLM is unavailable."""
    i = datetime.now().timetuple().tm_yday % len(_FALLBACK_MESSAGES)
    return _FALLBACK_MESSAGES[i]


def fallback_wallpaper_image_prompt() -> str:
    """Random English wallpaper prompt when image LLM is unavailable (Pinscrape still runs if enabled)."""
    return random.choice(_FALLBACK_WALLPAPER_PROMPTS)
