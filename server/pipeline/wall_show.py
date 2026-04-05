from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from domain.models import Scene, WallRun
from display.sink import DisplaySink
from renderers.template_base import RenderContext, SceneSlice
from renderers.registry import TemplateRegistry
from storage.paths import run_output_dir
from storage.stores import append_wall_run, new_wall_run_id, touch_last_shown


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class WallPipeline:
    def __init__(self, registry: TemplateRegistry, sink: DisplaySink) -> None:
        self._registry = registry
        self._sink = sink

    def run_scene(
        self,
        scene: Scene,
        frame_tuning: dict,
        device_profile: dict,
    ) -> WallRun:
        run_id = new_wall_run_id()
        started = _utc_iso()
        t0 = time.perf_counter()
        try:
            template = self._registry.get(scene.template_id)
            if not template:
                raise KeyError(f"unknown templateId: {scene.template_id}")
            out_dir = Path(run_output_dir(run_id))
            out_dir.mkdir(parents=True, exist_ok=True)
            
            ctx = RenderContext(
                scene=SceneSlice(
                    id=scene.id,
                    template_id=scene.template_id,
                    template_params=dict(scene.template_params or {}),
                ),
                frame_tuning=dict(frame_tuning or {}),
                device_profile=dict(device_profile or {}),
            )
            
            # The template now returns a PIL.Image.Image directly
            img = template.render(ctx)
            
            # Pipeline takes over saving the image
            out_path = out_dir / f"{scene.id}_{run_id}.png"
            img.save(out_path, format="PNG")
            image_path_str = str(out_path.resolve())
            
            self._sink.show(image_path_str)
            ms = int((time.perf_counter() - t0) * 1000)
            touch_last_shown(scene.id)
            run = WallRun(
                id=run_id,
                scene_id=scene.id,
                started_at=started,
                finished_at=_utc_iso(),
                duration_ms=ms,
                ok=True,
                error_message=None,
                output_path=image_path_str,
            )
            append_wall_run(run)
            return run
        except Exception as e:
            ms = int((time.perf_counter() - t0) * 1000)
            run = WallRun(
                id=run_id,
                scene_id=scene.id,
                started_at=started,
                finished_at=_utc_iso(),
                duration_ms=ms,
                ok=False,
                error_message=str(e),
                output_path=None,
            )
            append_wall_run(run)
            return run
