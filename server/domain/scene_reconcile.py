"""Align persisted scenes with installed templates."""

from __future__ import annotations

import uuid

from domain.models import AppConfig, IntervalSchedule, Scene
from renderers.registry import TemplateRegistry


def _unique_scene_id(template_id: str) -> str:
    safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in template_id)
    short_uuid = str(uuid.uuid4())[:8]
    return f"scene-{safe}-{short_uuid}"


def default_scene_for_template(template_id: str, *, display_name: str | None = None) -> Scene:
    label = (display_name or "").strip() or template_id
    return Scene(
        id=_unique_scene_id(template_id),
        name=label,
        description="",
        enabled=True,
        template_id=template_id,
        template_params={},
        schedule=IntervalSchedule(interval_seconds=300),
        preview_image_url=None,
        tie_break_priority=9,
    )


def _scenes_fill_empty_names(scenes: list[Scene], registry: TemplateRegistry) -> tuple[list[Scene], bool]:
    out: list[Scene] = []
    changed = False
    for s in scenes:
        if (s.name or "").strip():
            out.append(s)
            continue
        plug = registry.get(s.template_id)
        label = (plug.display_name if plug else None) or s.template_id
        out.append(s.model_copy(update={"name": label}))
        changed = True
    return out, changed


def reconcile_scenes_with_templates(cfg: AppConfig, registry: TemplateRegistry) -> tuple[AppConfig, bool]:
    """
    - Retain all scenes whose template_id is still in the registry.
    - Unknown template_ids (template removed): drop scenes.
    - Note: We NO LONGER append a default scene if a template has no scenes. It is perfectly valid for a template to have 0 instances.
    """
    valid_tids = set(registry.template_ids_ordered())
    
    new_scenes: list[Scene] = []
    
    for s in cfg.scenes:
        if s.template_id in valid_tids:
            new_scenes.append(s)

    new_scenes, _ = _scenes_fill_empty_names(new_scenes, registry)

    out = AppConfig(
        scenes=new_scenes,
        frame_tuning=cfg.frame_tuning,
        device_profile=cfg.device_profile,
        quiet_hours=cfg.quiet_hours,
    )
    if out.model_dump() == cfg.model_dump():
        return cfg, False
    return out, True
