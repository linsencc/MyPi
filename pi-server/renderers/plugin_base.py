from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class RenderResult:
    image_path: str


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
    output_dir: str


class WallTemplatePlugin(ABC):
    template_id: str
    display_name: str

    @abstractmethod
    def render(self, ctx: RenderContext) -> RenderResult:
        raise NotImplementedError
