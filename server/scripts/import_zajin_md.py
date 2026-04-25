"""Parse Obsidian 杂锦.md into _MISC_QUOTES block for misc_gallery/template.py."""
from __future__ import annotations

import re
from pathlib import Path

_MD = Path(r"c:\Users\xiewr\Documents\Obsidian Vault\生活杂记\杂锦.md")
_SECTIONS: tuple[tuple[int, int, str], ...] = (
    (0, 13, "# 节一：每个优秀的人，都有一段沉默的时光"),
    (13, 56, "# 节二：落日归山海，山海藏深意"),
    (56, 93, "# 节三：人生如逆旅，你我皆行人"),
    (93, 149, "# 随想"),
)


def _load_quotes() -> list[str]:
    md = _MD.read_text(encoding="utf-8")
    quotes: list[str] = []
    for line in md.splitlines():
        m = re.match(r"^(\d+)\.\s*(.+)$", line.strip())
        if m:
            quotes.append(m.group(2).strip().replace("*", ""))
    return quotes


def emit_tuple() -> str:
    quotes = _load_quotes()
    if len(quotes) != 149:
        raise SystemExit(f"expected 149 items, got {len(quotes)}")
    lines = [
        "_MISC_QUOTES: tuple[str, ...] = (",
        "    # 与 Obsidian《杂锦.md》编号条目一一对应（一条一行，不合并）。",
    ]
    for start, end, title in _SECTIONS:
        lines.append(f"    {title}")
        for s in quotes[start:end]:
            lines.append(f"    {repr(s)},")
    lines.append(")")
    return "\n".join(lines) + "\n"


def apply_to_misc_gallery() -> None:
    """Rewrite _MISC_QUOTES in renderers/templates/misc_gallery/template.py from Obsidian md."""
    root = Path(__file__).resolve().parents[2]
    tpl = root / "server" / "renderers" / "templates" / "misc_gallery" / "template.py"
    main = tpl.read_text(encoding="utf-8")
    start = main.index("_MISC_QUOTES:")
    end = main.index("\ndef _line_width", start)
    tpl.write_text(main[:start] + emit_tuple().rstrip() + "\n" + main[end:], encoding="utf-8")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--apply":
        apply_to_misc_gallery()
        print("updated misc_gallery/template.py", file=sys.stderr)
    else:
        print(emit_tuple(), end="")
