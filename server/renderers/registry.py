from __future__ import annotations

import importlib
import inspect
import pkgutil

from renderers import templates as templates_pkg
from renderers.template_base import WallTemplate


class TemplateRegistry:
    def __init__(self, templates: dict[str, WallTemplate]) -> None:
        self._by_id = templates

    def get(self, template_id: str) -> WallTemplate | None:
        return self._by_id.get(template_id)

    def template_ids_ordered(self) -> list[str]:
        return sorted(self._by_id.keys())

    def all_metadata(self) -> list[dict[str, str]]:
        return [
            {"templateId": p.template_id, "displayName": p.display_name}
            for p in sorted(self._by_id.values(), key=lambda x: x.template_id)
        ]


def discover_templates() -> TemplateRegistry:
    found: dict[str, WallTemplate] = {}
    for info in pkgutil.iter_modules(templates_pkg.__path__):
        if info.ispkg:
            continue
        mod = importlib.import_module(f"{templates_pkg.__name__}.{info.name}")
        for _n, obj in inspect.getmembers(mod):
            if isinstance(obj, type) and issubclass(obj, WallTemplate) and obj is not WallTemplate:
                inst = obj()
                tid = getattr(type(inst), "template_id", None) or getattr(inst, "template_id", None)
                if not tid:
                    continue
                if tid in found:
                    raise RuntimeError(f"duplicate template_id: {tid}")
                found[tid] = inst
        tmpl = getattr(mod, "template", None)
        if isinstance(tmpl, WallTemplate):
            tid = tmpl.template_id
            if tid in found:
                raise RuntimeError(f"duplicate template_id: {tid}")
            found[tid] = tmpl
    return TemplateRegistry(found)
