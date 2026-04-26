from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from PIL.Image import Image


@dataclass(frozen=True)
class SceneSlice:
    id: str
    template_id: str
    template_params: dict


@dataclass(frozen=True)
class RenderContext:
    scene: SceneSlice
    frame_tuning: dict
    device_profile: dict


class WallTemplate(ABC):
    display_name: str
    #: ``GET /templates`` → ``paramSchema``。由模板包维护（``param_schema.json`` 或
    #: ``renderers.templates.ui_params``）；场景落库时的 ``templateParams`` 规范化见
    #: ``renderers.templates.ui_params.normalize_scene_template_params``（路由层调用，不在此基类实现）。
    param_schema: ClassVar[list[dict[str, Any]]] = []

    @abstractmethod
    def render(self, ctx: RenderContext) -> Image:
        raise NotImplementedError
