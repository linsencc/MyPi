from .plugin_base import RenderContext, RenderResult, SceneSlice, WallTemplatePlugin
from .registry import discover_plugins, PluginRegistry

__all__ = [
    "RenderContext",
    "RenderResult",
    "SceneSlice",
    "WallTemplatePlugin",
    "discover_plugins",
    "PluginRegistry",
]
