from __future__ import annotations

import importlib
import inspect
import pkgutil

from renderers import plugins as plugins_pkg
from renderers.plugin_base import WallTemplatePlugin


class PluginRegistry:
    def __init__(self, plugins: dict[str, WallTemplatePlugin]) -> None:
        self._by_id = plugins

    def get(self, template_id: str) -> WallTemplatePlugin | None:
        return self._by_id.get(template_id)

    def template_ids_ordered(self) -> list[str]:
        return sorted(self._by_id.keys())

    def all_metadata(self) -> list[dict[str, str]]:
        return [
            {"templateId": p.template_id, "displayName": p.display_name}
            for p in sorted(self._by_id.values(), key=lambda x: x.template_id)
        ]


def discover_plugins() -> PluginRegistry:
    found: dict[str, WallTemplatePlugin] = {}
    for info in pkgutil.iter_modules(plugins_pkg.__path__):
        if info.ispkg:
            continue
        mod = importlib.import_module(f"{plugins_pkg.__name__}.{info.name}")
        for _n, obj in inspect.getmembers(mod):
            if isinstance(obj, type) and issubclass(obj, WallTemplatePlugin) and obj is not WallTemplatePlugin:
                inst = obj()
                tid = getattr(type(inst), "template_id", None) or getattr(inst, "template_id", None)
                if not tid:
                    continue
                if tid in found:
                    raise RuntimeError(f"duplicate template_id: {tid}")
                found[tid] = inst
        plug = getattr(mod, "plugin", None)
        if isinstance(plug, WallTemplatePlugin):
            tid = plug.template_id
            if tid in found:
                raise RuntimeError(f"duplicate template_id: {tid}")
            found[tid] = plug
    return PluginRegistry(found)
