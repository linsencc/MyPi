"""Jinja2 HTML for 周末出行 wall template."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

_RENDER_DIR = Path(__file__).resolve().parent / "render"
_FONT_CANDIDATE = Path(__file__).resolve().parent.parent / "fonts" / "NotoSansSC-Regular.otf"


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
    return tpl.render(**ctx)
