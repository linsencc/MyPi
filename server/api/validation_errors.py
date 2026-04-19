"""Format Pydantic ValidationError for HTTP JSON responses."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError


def scene_validation_error_response(exc: ValidationError) -> dict[str, Any]:
    """Return a JSON-serializable body with a short ``error`` and optional ``details``."""
    raw = exc.errors(include_input=False, include_url=False)
    details: list[dict[str, Any]] = []
    for e in raw:
        item: dict[str, Any] = {
            "loc": [str(x) for x in e.get("loc", ())],
            "msg": str(e.get("msg", "")),
            "type": str(e.get("type", "")),
        }
        if "ctx" in e and e["ctx"] is not None:
            ctx = e["ctx"]
            safe: dict[str, str] = {}
            for k, v in ctx.items():
                safe[str(k)] = str(v)
            item["ctx"] = safe
        details.append(item)

    schedule_only = bool(raw) and all(
        len(e.get("loc", ())) >= 1 and e["loc"][0] == "schedule" for e in raw
    )
    prefix = "Invalid schedule: " if schedule_only else "Invalid scene: "

    parts: list[str] = []
    for e in raw[:3]:
        loc = e.get("loc") or ()
        loc_s = " → ".join(str(x) for x in loc)
        msg = str(e.get("msg", "validation error"))
        if msg.startswith("Value error, "):
            msg = msg[len("Value error, ") :]
        parts.append(f"{loc_s}: {msg}" if loc_s else msg)
    body = "; ".join(parts)
    if len(raw) > 3:
        body += f" (+{len(raw) - 3} more)"

    return {"error": prefix + body, "details": details}
