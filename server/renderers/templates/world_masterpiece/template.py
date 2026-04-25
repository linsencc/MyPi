"""Famous paintings: prefer bundled JPEGs under masterpieces/, else Wikimedia Commons; caption + bottom scrim."""

from __future__ import annotations

import logging
import os
import random
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance

from renderers.template_base import RenderContext, WallTemplate
from renderers.templates.cjk_font import _load_cjk_font, _wrap_lines
from renderers.templates.cn_date import cn_date_str
from renderers.templates.photo_scrim import (
    build_remote_image_opener,
    download_image_url,
    fit_image_cover,
    overlay_bottom_scrim,
    to_full_color_rgb,
)

log = logging.getLogger(__name__)

# Wikimedia requires a descriptive User-Agent (not a generic browser bot string).
_WIKIMEDIA_UA = "MyPiWallDisplay/1.0 (wall template; +https://github.com/)"

# Hard cap for download phase so gunicorn --timeout (120s) is not exceeded.
_FETCH_BUDGET_S = 72.0
_MAX_PAINTING_TRIES = 4


@dataclass(frozen=True)
class _Painting:
    title: str
    artist: str
    description: str
    image_url: str
    asset_file: str | None = None


# Bundled JPEGs in this package's masterpieces/ (see server/scripts/fetch_world_masterpiece_assets.py).
_MASTERPIECES_DIR = Path(__file__).resolve().parent / "masterpieces"

# Wikimedia Commons; public-domain or freely licensed masterpieces.
_PAINTINGS: tuple[_Painting, ...] = (
    _Painting(
        "星夜",
        "文森特·梵高（荷兰）",
        "旋涡状的星空与火焰般的丝柏占据夜空，下方是静谧的欧洲小镇。后印象派的笔触与强烈色彩传递出躁动与安宁并存的夜晚。",
        "https://upload.wikimedia.org/wikipedia/commons/e/ea/Van_Gogh_-_Starry_Night_-_Google_Art_Project.jpg",
        "starry_night.jpg",
    ),
    _Painting(
        "蒙娜丽莎",
        "列奥纳多·达·芬奇（意大利）",
        "文艺复兴肖像的典范，神秘的微笑与渐隐法晕染的面部，背景山水与人物融为一体，含蓄而永恒。",
        "https://upload.wikimedia.org/wikipedia/commons/e/ec/Mona_Lisa%2C_by_Leonardo_da_Vinci%2C_from_C2RMF_retouched.jpg",
        "mona_lisa.jpg",
    ),
    _Painting(
        "神奈川冲浪里",
        "葛饰北斋（日本）",
        "浮世绘巨浪与富士山的经典构图，浪峰如爪、动势惊人，展现自然之力与人的渺小。",
        "https://upload.wikimedia.org/wikipedia/commons/a/a5/Tsunami_by_hokusai_19th_century.jpg",
        "great_wave.jpg",
    ),
    _Painting(
        "戴珍珠耳环的少女",
        "约翰内斯·维米尔（荷兰）",
        "柔和侧光落在少女面颊与蓝色头巾上，珍珠成为视觉焦点，静谧中带着一丝回眸的叙事感。",
        "https://upload.wikimedia.org/wikipedia/commons/6/66/Johannes_Vermeer_%281632-1675%29_-_The_Girl_With_The_Pearl_Earring_%281665%29.jpg",
        "girl_pearl_earring.jpg",
    ),
    _Painting(
        "维纳斯的诞生",
        "桑德罗·波提切利（意大利）",
        "风神将维纳斯送至岸边，线条修长优雅，色彩清澈如釉，是文艺复兴早期神话题材的诗意呈现。",
        "https://upload.wikimedia.org/wikipedia/commons/f/f2/Botticelli_-_La_nascita_di_Venere_-_Google_Art_Project.jpg",
        "birth_venus.jpg",
    ),
    _Painting(
        "印象·日出",
        "克劳德·莫奈（法国）",
        "橙红日轮与朦胧港湾启发了「印象派」之名，笔触迅疾、雾汽氤氲，捕捉瞬间的光色而非细节。",
        "https://upload.wikimedia.org/wikipedia/commons/5/59/Monet_-_Impression%2C_Sunrise.jpg",
        "impression_sunrise.jpg",
    ),
    _Painting(
        "睡莲",
        "克劳德·莫奈（法国）",
        "吉维尼池塘上的睡莲与倒影，色点交融、边界消融，晚期作品在抽象边缘探索光与水的无尽变化。",
        "https://upload.wikimedia.org/wikipedia/commons/6/69/Claude_Monet_-_Water_Lilies_-_Google_Art_Project.jpg",
        "water_lilies.jpg",
    ),
    _Painting(
        "吻",
        "古斯塔夫·克里姆特（奥地利）",
        "金箔与几何纹样包裹恋人，装饰性与情感张力并存，是新艺术运动与象征主义的华丽高峰。",
        "https://upload.wikimedia.org/wikipedia/commons/7/7d/Gustav_Klimt_016.jpg",
        "kiss_klimt.jpg",
    ),
    _Painting(
        "记忆的永恒",
        "萨尔瓦多·达利（西班牙）",
        "融化的怀表与荒凉海岸构成超现实梦境，探讨时间、记忆与潜意识的暧昧关系。",
        "https://upload.wikimedia.org/wikipedia/commons/d/dd/The_Persistence_of_Memory.jpg",
        None,
    ),
    _Painting(
        "美国哥特式",
        "格兰特·伍德（美国）",
        "中西部农舍前神情肃穆的父女与干草叉，既是乡土写实，也成为美国意象的符号化肖像。",
        "https://upload.wikimedia.org/wikipedia/commons/f/f3/Grant_Wood_-_American_Gothic_-_Google_Art_Project.jpg",
        "american_gothic.jpg",
    ),
    _Painting(
        "夜巡",
        "伦勃朗（荷兰）",
        "群像民兵在光影中出场，戏剧性的明暗与人物层次打破传统排排站的集体肖像范式。",
        "https://upload.wikimedia.org/wikipedia/commons/2/28/De_Nachtwacht.jpg",
        "night_watch.jpg",
    ),
    _Painting(
        "宫娥",
        "迭戈·委拉斯开兹（西班牙）",
        "画室中的公主、宫娥与镜中国王夫妇，观看与被观看的关系在纵深空间里层层嵌套。",
        "https://upload.wikimedia.org/wikipedia/commons/5/57/Las_Meninas%2C_by_Diego_Vel%C3%A1zquez%2C_from_Prado_in_Google_Art_Project.jpg",
        "las_meninas.jpg",
    ),
    _Painting(
        "向日葵",
        "文森特·梵高（荷兰）",
        "瓶中金灿向日葵以厚涂与纯色并置，笔触如火焰，是生命力与孤独并存的静物绝唱。",
        "https://upload.wikimedia.org/wikipedia/commons/4/46/Vincent_van_Gogh_-_Sunflowers_-_VGM_F458.jpg",
        "sunflowers.jpg",
    ),
    _Painting(
        "呐喊",
        "爱德华·蒙克（挪威）",
        "血红色天空下扭曲的身影与桥上的无声尖叫，表现主义地外化了现代人的焦虑与不安。",
        "https://upload.wikimedia.org/wikipedia/commons/f/f4/The_Scream.jpg",
        "the_scream.jpg",
    ),
    _Painting(
        "雾海上的旅人",
        "卡斯帕·大卫·弗里德里希（德国）",
        "背影立于山巅俯瞰云海，浪漫主义的崇高与孤独在开阔天地间同时升起。",
        "https://upload.wikimedia.org/wikipedia/commons/b/b9/Caspar_David_Friedrich_-_Wanderer_above_the_sea_of_fog.jpg",
        "wanderer_fog.jpg",
    ),
    _Painting(
        "大碗岛的星期天下午",
        "乔治·修拉（法国）",
        "以点彩技法描绘河畔休闲人群，阳光与草地由色点并置混合，是新印象派对科学与光色的实验。",
        "https://upload.wikimedia.org/wikipedia/commons/7/7d/Georges_Seurat_-_A_Sunday_on_La_Grande_Jatte_-_Google_Art_Project.jpg",
        "sunday_jatte.jpg",
    ),
    _Painting(
        "干草车",
        "约翰·康斯特布尔（英国）",
        "英格兰乡村浅滩马车与茂密林木，自然主义的光影与云层，寄托对乡土宁静的理想化凝视。",
        "https://upload.wikimedia.org/wikipedia/commons/3/35/John_Constable_-_The_Hay_Wain.jpg",
        "hay_wain.jpg",
    ),
    _Painting(
        "煎饼磨坊的舞会",
        "皮埃尔-奥古斯特·雷诺阿（法国）",
        "蒙马特露天舞场阳光斑驳，人物衣饰与树叶闪烁，印象派捕捉欢乐瞬间的轻松笔调。",
        "https://upload.wikimedia.org/wikipedia/commons/4/46/Pierre-Auguste_Renoir%2C_Le_Moulin_de_la_Galette.jpg",
        "moulin_galette.jpg",
    ),
    _Painting(
        "灰与黑的协奏曲：画家母亲肖像",
        "詹姆斯·惠斯勒（美国）",
        "侧坐的老妇人与素墙形成极简构图，灰阶节奏冷静克制，是「为艺术而艺术」的审美宣言。",
        "https://upload.wikimedia.org/wikipedia/commons/1/1b/Whistlers_Mother_high_res.jpg",
        "whistlers_mother.jpg",
    ),
    _Painting(
        "创造亚当",
        "米开朗基罗（意大利）",
        "西斯廷天顶画中上帝与亚当指尖将触未触的瞬间，人体力量与神性张力凝于一臂之间。",
        "https://upload.wikimedia.org/wikipedia/commons/2/22/Michelangelo_-_Creation_of_Adam_%28cropped%29.jpg",
        "creation_adam.jpg",
    ),
)

_BG = (250, 248, 243)
_TEXT = (30, 32, 36)
_SECONDARY = (110, 105, 98)
_SUBTLE = (150, 145, 138)
_ACCENT = (85, 80, 72)
_QUOTE_FILL = (244, 240, 228)
_QUOTE_STROKE = (10, 12, 18)
_FOOTER_A = (188, 182, 170)
_FOOTER_B = (138, 132, 122)
_TITLE_ON_SCRIM = (232, 228, 218)
_ARTIST_ON_SCRIM = (178, 172, 162)


def _max_long_edge() -> int:
    raw = os.environ.get("MYPI_MASTERPIECE_MAX_SIDE", "2400").strip()
    try:
        v = int(raw)
    except ValueError:
        v = 2400
    return max(640, min(v, 4096))


def _limit_long_edge(img: Image.Image, max_side: int | None = None) -> Image.Image:
    cap = max_side if max_side is not None else _max_long_edge()
    w, h = img.size
    if max(w, h) <= cap:
        return img
    if w >= h:
        nh = max(1, int(round(h * cap / w)))
        return img.resize((cap, nh), Image.LANCZOS)
    nw = max(1, int(round(w * cap / h)))
    return img.resize((nw, cap), Image.LANCZOS)


def _mild_enhance(img: Image.Image) -> Image.Image:
    rgb = img.convert("RGB")
    rgb = ImageEnhance.Contrast(rgb).enhance(1.04)
    rgb = ImageEnhance.Color(rgb).enhance(1.03)
    rgb = ImageEnhance.Sharpness(rgb).enhance(1.05)
    return rgb


def _compose_with_image(
    p: _Painting,
    art: Image.Image,
    canvas_w: int,
    canvas_h: int,
) -> Image.Image:
    img = Image.new("RGB", (canvas_w, canvas_h), _BG)
    fitted = fit_image_cover(art, canvas_w, canvas_h)
    fitted = _mild_enhance(fitted)
    img.paste(fitted, (0, 0))

    scrim_start = int(canvas_h * 0.46)
    overlay_bottom_scrim(
        img,
        scrim_start,
        canvas_h - scrim_start,
        max_opacity_env="MYPI_MASTERPIECE_SCRIM_MAX",
        default_max_opacity=0.74,
    )
    draw = ImageDraw.Draw(img)

    scale = min(canvas_w, canvas_h) / 600
    margin_x = max(28, int(canvas_w * 0.065))

    title_px = max(15, int(20 * scale))
    artist_px = max(12, int(16 * scale))
    desc_px = max(11, int(14 * scale))
    footer_px = max(10, int(11 * scale))

    font_title = _load_cjk_font(title_px)
    font_artist = _load_cjk_font(artist_px)
    font_desc = _load_cjk_font(desc_px)
    font_footer = _load_cjk_font(footer_px)

    title_text = f"《{p.title}》"
    raw_max = max(7, int((canvas_w - margin_x * 2) / (desc_px * 1.02)))
    desc_lines = _wrap_lines(p.description, max_chars=raw_max, max_lines=5)

    line_h_desc = int(desc_px * 1.38)

    gap_ta = int(5 * scale)
    gap_mid = int(9 * scale)
    gap_f = int(11 * scale)
    margin_bottom = int(17 * scale)

    tb = draw.textbbox((0, 0), title_text, font=font_title)
    title_w = tb[2] - tb[0]
    title_h = tb[3] - tb[1]

    ab = draw.textbbox((0, 0), p.artist, font=font_artist)
    artist_h = ab[3] - ab[1]

    desc_h = len(desc_lines) * line_h_desc
    footer_h = footer_px + 4

    total_h = title_h + gap_ta + artist_h + gap_mid + desc_h + gap_f + footer_h
    y0 = canvas_h - margin_bottom - total_h

    tx = (canvas_w - title_w) // 2
    draw.text(
        (tx, y0),
        title_text,
        fill=_TITLE_ON_SCRIM,
        font=font_title,
        stroke_width=max(1, int(1.2 * scale)),
        stroke_fill=_QUOTE_STROKE,
    )

    y_art = y0 + title_h + gap_ta
    aw = ab[2] - ab[0]
    draw.text(
        ((canvas_w - aw) // 2, y_art),
        p.artist,
        fill=_ARTIST_ON_SCRIM,
        font=font_artist,
        stroke_width=max(1, int(1.0 * scale)),
        stroke_fill=_QUOTE_STROKE,
    )

    y_desc = y_art + artist_h + gap_mid
    stroke_d = max(1, int(1.35 * scale))
    for k, ln in enumerate(desc_lines):
        bbox = draw.textbbox((0, 0), ln, font=font_desc)
        tw = bbox[2] - bbox[0]
        draw.text(
            ((canvas_w - tw) // 2, y_desc + k * line_h_desc),
            ln,
            fill=_QUOTE_FILL,
            font=font_desc,
            stroke_width=stroke_d,
            stroke_fill=_QUOTE_STROKE,
        )

    footer_y = y_desc + desc_h + gap_f
    date_str = cn_date_str()
    attr_str = "— 世界名画"
    spacer = int(16 * scale)
    db = draw.textbbox((0, 0), date_str, font=font_footer)
    abf = draw.textbbox((0, 0), attr_str, font=font_footer)
    dw, awf = db[2] - db[0], abf[2] - abf[0]
    total = dw + spacer + awf
    x0 = (canvas_w - total) // 2
    draw.text((x0, footer_y), date_str, fill=_FOOTER_A, font=font_footer)
    draw.text((x0 + dw + spacer, footer_y), attr_str, fill=_FOOTER_B, font=font_footer)

    return img


def _compose_text_only(p: _Painting, canvas_w: int, canvas_h: int) -> Image.Image:
    img = Image.new("RGB", (canvas_w, canvas_h), _BG)
    draw = ImageDraw.Draw(img)
    scale = min(canvas_w, canvas_h) / 600
    cx = canvas_w // 2
    margin = max(32, int(canvas_w * 0.07))

    bar_w = int(28 * scale)
    bar_h = max(1, int(2 * scale))
    bar_y = int(canvas_h * 0.26)
    draw.rectangle(
        [(cx - bar_w // 2, bar_y), (cx + bar_w // 2, bar_y + bar_h)],
        fill=_ACCENT,
    )

    title_px = max(17, int(22 * scale))
    artist_px = max(14, int(17 * scale))
    desc_px = max(13, int(16 * scale))
    font_title = _load_cjk_font(title_px)
    font_artist = _load_cjk_font(artist_px)
    font_desc = _load_cjk_font(desc_px)

    title_text = f"《{p.title}》"
    y = bar_y + bar_h + int(18 * scale)

    tb = draw.textbbox((0, 0), title_text, font=font_title)
    tw = tb[2] - tb[0]
    draw.text(((canvas_w - tw) // 2, y), title_text, fill=_TEXT, font=font_title)
    y += int(title_px * 1.45)

    ab = draw.textbbox((0, 0), p.artist, font=font_artist)
    aw = ab[2] - ab[0]
    draw.text(((canvas_w - aw) // 2, y), p.artist, fill=_SECONDARY, font=font_artist)
    y += int(artist_px * 1.5) + int(8 * scale)

    raw_max = max(6, int((canvas_w - margin * 2) / (desc_px * 1.05)))
    lines = _wrap_lines(p.description, max_chars=raw_max, max_lines=6)
    line_h = int(desc_px * 1.42)
    for ln in lines:
        bbox = draw.textbbox((0, 0), ln, font=font_desc)
        lw = bbox[2] - bbox[0]
        draw.text(((canvas_w - lw) // 2, y), ln, fill=_TEXT, font=font_desc)
        y += line_h

    y += int(16 * scale)
    small = _load_cjk_font(max(10, int(12 * scale)))
    date_str = cn_date_str()
    attr_str = "— 世界名画"
    spacer = int(18 * scale)
    db = draw.textbbox((0, 0), date_str, font=small)
    abf = draw.textbbox((0, 0), attr_str, font=small)
    dw, awf = db[2] - db[0], abf[2] - abf[0]
    total = dw + spacer + awf
    x0 = (canvas_w - total) // 2
    draw.text((x0, y), date_str, fill=_SECONDARY, font=small)
    draw.text((x0 + dw + spacer, y), attr_str, fill=_SUBTLE, font=small)

    return img


def _download_painting_url(
    url: str,
    opener: urllib.request.OpenerDirector,
    max_side: int,
) -> Image.Image | None:
    """Direct Commons URL; connect/read split in photo_scrim avoids long SSL hangs."""
    per_try_timeout = 28
    raw = os.environ.get("MYPI_MASTERPIECE_HTTP_TIMEOUT", "").strip()
    if raw:
        try:
            per_try_timeout = max(12, min(45, int(raw)))
        except ValueError:
            pass
    art = download_image_url(
        url,
        opener,
        timeout=per_try_timeout,
        log_prefix="world_masterpiece",
        user_agent=_WIKIMEDIA_UA,
        retries=1,
        retry_delay_s=0.0,
    )
    if art is None:
        return None
    return _limit_long_edge(art, max_side)


def _load_painting_raster(
    p: _Painting,
    opener: urllib.request.OpenerDirector,
    max_side: int,
) -> Image.Image | None:
    """Prefer bundled JPEG under masterpieces/ so the frame works offline or behind strict firewalls."""
    if p.asset_file:
        local = _MASTERPIECES_DIR / p.asset_file
        if local.is_file():
            try:
                with Image.open(local) as im:
                    rgb = to_full_color_rgb(im.convert("RGB"))
                log.info("world_masterpiece: using local asset %s", p.asset_file)
                return _limit_long_edge(rgb, max_side)
            except OSError as exc:
                log.warning("world_masterpiece: local asset unreadable %s: %s", p.asset_file, exc)
    return _download_painting_url(p.image_url, opener, max_side)


class WorldMasterpieceTemplate(WallTemplate):
    display_name = "世界名画"

    def render(self, ctx: RenderContext) -> Image.Image:
        w = ctx.device_profile.get("width", 800)
        h = ctx.device_profile.get("height", 600)

        order = list(range(len(_PAINTINGS)))
        random.shuffle(order)
        deadline = time.monotonic() + _FETCH_BUDGET_S
        opener = build_remote_image_opener()
        cap = _max_long_edge()
        for j in range(min(_MAX_PAINTING_TRIES, len(_PAINTINGS))):
            if time.monotonic() > deadline:
                log.warning("world_masterpiece: fetch budget exhausted; text-only fallback")
                break
            p = _PAINTINGS[order[j]]
            art = _load_painting_raster(p, opener, cap)
            if art is not None:
                return _compose_with_image(p, art, w, h)

        p = _PAINTINGS[order[0]]
        log.warning("world_masterpiece: all downloads failed; text-only fallback")
        return _compose_text_only(p, w, h)
