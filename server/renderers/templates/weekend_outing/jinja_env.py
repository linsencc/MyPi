"""Jinja2 HTML for 周末出行 wall template."""

from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

_RENDER_DIR = Path(__file__).resolve().parent / "render"
_FONT_CANDIDATE = Path(__file__).resolve().parent.parent / "fonts" / "NotoSansSC-Regular.otf"
_BOOTSTRAP_ICONS_VEND = _RENDER_DIR / "vendor" / "bootstrap-icons"
_BOOTSTRAP_ICONS_CSS_CACHE: str | None = None


def _font_face_block() -> str:
    if not _FONT_CANDIDATE.is_file():
        return ""
    uri = _FONT_CANDIDATE.resolve().as_uri()
    return f"""@font-face {{
  font-family: "MyPiWeekend";
  font-weight: 400;
  font-style: normal;
  src: url("{uri}") format("opentype");
}}"""


def _embedded_bootstrap_icons_css() -> str:
    """Inline min CSS + woff2 as data URL so ``file://`` Chromium render needs no font files."""
    global _BOOTSTRAP_ICONS_CSS_CACHE
    if _BOOTSTRAP_ICONS_CSS_CACHE is not None:
        return _BOOTSTRAP_ICONS_CSS_CACHE
    css_p = _BOOTSTRAP_ICONS_VEND / "bootstrap-icons.min.css"
    w2 = _BOOTSTRAP_ICONS_VEND / "fonts" / "bootstrap-icons.woff2"
    if not css_p.is_file() or not w2.is_file():
        _BOOTSTRAP_ICONS_CSS_CACHE = ""
        return ""
    b64 = base64.b64encode(w2.read_bytes()).decode("ascii")
    css = css_p.read_text(encoding="utf-8")
    css = re.sub(
        r'url\("fonts/bootstrap-icons\.woff2[^"]*"\)\s*format\("woff2"\)\s*,\s*url\("fonts/bootstrap-icons\.woff[^"]*"\)\s*format\("woff"\)',
        f'url("data:font/woff2;base64,{b64}") format("woff2")',
        css,
        count=1,
    )
    _BOOTSTRAP_ICONS_CSS_CACHE = css
    return css


def render_weekend_layout_html(context: dict[str, Any]) -> str:
    """Render ``layout.html`` with embedded ``weekend.css``."""
    env = Environment(
        loader=FileSystemLoader(str(_RENDER_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    css_text = (_RENDER_DIR / "weekend.css").read_text(encoding="utf-8")
    tpl = env.get_template("layout.html")
    ctx = dict(context)
    ctx.setdefault("embedded_css", css_text)
    ctx.setdefault("font_face_css", _font_face_block())
    ctx.setdefault("bootstrap_icons_css", _embedded_bootstrap_icons_css())
    ctx.setdefault("hero_meta", "")
    ctx.setdefault("hero_lede", "")
    ctx.setdefault("advice_lead", str(ctx.get("rule") or ""))
    ctx.setdefault("advice_bullets", [])
    ctx.setdefault("advice_bullets_html", [])
    ctx.setdefault("advice_sub", str(ctx.get("area_label") or ""))
    ctx.setdefault("frame_scale", 1.0)
    ctx.setdefault("frame_off_x", 0.0)
    ctx.setdefault("frame_off_y", 0.0)
    return tpl.render(**ctx)
