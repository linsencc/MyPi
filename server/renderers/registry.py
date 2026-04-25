from __future__ import annotations

import importlib
import inspect
import pkgutil
import re

from renderers import templates as templates_pkg
from renderers.template_base import WallTemplate


def _to_snake_case(name: str) -> str:
    name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    name = re.sub("([a-z0-9])([A-Z])", r"\1_\2", name)
    return name.lower()


class TemplateRegistry:
    def __init__(self, templates: dict[str, WallTemplate]) -> None:
        self._by_id = templates

    def get(self, template_id: str) -> WallTemplate | None:
        return self._by_id.get(template_id)

    def template_ids_ordered(self) -> list[str]:
        return sorted(self._by_id.keys())

    def all_metadata(self) -> list[dict[str, str]]:
        return [
            {"templateId": tid, "displayName": inst.display_name}
            for tid, inst in sorted(self._by_id.items(), key=lambda x: x[0])
        ]


def _register_wall_templates_from_module(mod, found: dict[str, WallTemplate]) -> None:
    for _n, obj in inspect.getmembers(mod):
        if isinstance(obj, type) and issubclass(obj, WallTemplate) and obj is not WallTemplate:
            inst = obj()
            tid = _to_snake_case(obj.__name__)
            if tid.endswith("_template"):
                tid = tid[:-9]
            if tid in found:
                raise RuntimeError(f"duplicate template_id: {tid}")
            found[tid] = inst
    tmpl = getattr(mod, "template", None)
    if isinstance(tmpl, WallTemplate):
        tid = _to_snake_case(tmpl.__class__.__name__)
        if tid.endswith("_template"):
            tid = tid[:-9]
        if tid in found:
            raise RuntimeError(f"duplicate template_id: {tid}")
        found[tid] = tmpl


def discover_templates() -> TemplateRegistry:
    found: dict[str, WallTemplate] = {}
    # Top-level .py in templates/ (shared helpers: photo_scrim, cjk_font, …)
    for info in pkgutil.iter_modules(templates_pkg.__path__):
        if info.ispkg:
            continue
        if info.name.startswith("_"):
            continue
        mod = importlib.import_module(f"{templates_pkg.__name__}.{info.name}")
        _register_wall_templates_from_module(mod, found)
    # One feature folder per wall template, e.g. world_masterpiece/, ai_motto/, misc_gallery/
    for info in pkgutil.iter_modules(templates_pkg.__path__):
        if not info.ispkg or info.name.startswith("_"):
            continue
        try:
            pkg = importlib.import_module(f"{templates_pkg.__name__}.{info.name}")
        except ImportError:
            continue
        if not hasattr(pkg, "__path__"):
            continue
        for sub in pkgutil.walk_packages(pkg.__path__, f"{pkg.__name__}."):
            if sub.ispkg:
                continue
            submod = importlib.import_module(sub.name)
            _register_wall_templates_from_module(submod, found)
    return TemplateRegistry(found)
