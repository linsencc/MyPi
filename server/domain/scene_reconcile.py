"""Align persisted scenes with installed templates: one schedulable row per template_id."""

from __future__ import annotations

from domain.models import AppConfig, IntervalSchedule, Scene
from renderers.registry import TemplateRegistry


def _stable_scene_id(template_id: str) -> str:
    safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in template_id)
    return f"scene-{safe}"


def default_scene_for_template(template_id: str, *, display_name: str | None = None) -> Scene:
    label = (display_name or "").strip() or template_id
    return Scene(
        id=_stable_scene_id(template_id),
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
    - One scene per registered template_id (registry order).
    - Duplicate template_ids in file: keep first occurrence, drop later.
    - Unknown template_ids (template removed): drop scenes.
    - Missing template_ids: append default scene.
    """
    ordered_ids = registry.template_ids_ordered()
    by_tid: dict[str, Scene] = {}
    order_first: list[str] = []
    for s in cfg.scenes:
        tid = s.template_id
        if tid not in by_tid:
            by_tid[tid] = s
            order_first.append(tid)

    new_scenes: list[Scene] = []
    for tid in ordered_ids:
        if tid in by_tid:
            new_scenes.append(by_tid[tid])
        else:
            plug = registry.get(tid)
            dn = (plug.display_name if plug else None) or tid
            new_scenes.append(default_scene_for_template(tid, display_name=dn))

    new_scenes, _ = _scenes_fill_empty_names(new_scenes, registry)

    out = AppConfig(
        scenes=new_scenes,
        frame_tuning=cfg.frame_tuning,
        device_profile=cfg.device_profile,
    )
    if out.model_dump() == cfg.model_dump():
        return cfg, False
    return out, True
