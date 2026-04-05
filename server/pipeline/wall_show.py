from __future__ import annotations

import time
from datetime import datetime, timezone

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
            out_dir = str(run_output_dir(run_id))
            ctx = RenderContext(
                scene=SceneSlice(
                    id=scene.id,
                    template_id=scene.template_id,
                    template_params=dict(scene.template_params or {}),
                ),
                frame_tuning=dict(frame_tuning or {}),
                device_profile=dict(device_profile or {}),
                output_dir=out_dir,
            )
            result = template.render(ctx)
            self._sink.show(result.image_path)
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
                output_path=result.image_path,
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
