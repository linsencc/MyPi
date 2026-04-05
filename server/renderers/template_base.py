from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

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

    @abstractmethod
    def render(self, ctx: RenderContext) -> Image:
        raise NotImplementedError
