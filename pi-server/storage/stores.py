from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from domain.models import AppConfig, WallRun
from domain.scene_reconcile import default_scene_for_template
from storage.paths import config_path, schedule_state_path, wall_runs_path

if TYPE_CHECKING:
    from renderers.registry import PluginRegistry

_registry: PluginRegistry | None = None


def set_config_registry(reg: PluginRegistry | None) -> None:
    global _registry
    _registry = reg


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def default_config() -> AppConfig:
    s = default_scene_for_template("daily_motto", display_name="每日寄语")
    return AppConfig(scenes=[s])


def _dedupe_scenes_in_raw(raw: dict[str, Any]) -> dict[str, Any]:
    scenes = raw.get("scenes")
    if not isinstance(scenes, list):
        return raw
    seen: set[str] = set()
    out: list[Any] = []
    for item in scenes:
        if not isinstance(item, dict):
            out.append(item)
            continue
        tid = item.get("templateId")
        if not isinstance(tid, str) or not tid:
            out.append(item)
            continue
        if tid in seen:
            continue
        seen.add(tid)
        out.append(item)
    return {**raw, "scenes": out}


def load_config() -> AppConfig:
    p = config_path()
    if not p.is_file():
        cfg = default_config()
        save_config(cfg)
        return cfg
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raw = {}
    raw = _dedupe_scenes_in_raw(raw)
    cfg = AppConfig.model_validate(raw)
    if _registry is not None:
        from domain.scene_reconcile import reconcile_scenes_with_plugins

        cfg2, changed = reconcile_scenes_with_plugins(cfg, _registry)
        if changed:
            save_config(cfg2)
        return cfg2
    return cfg


def save_config(cfg: AppConfig) -> None:
    p = config_path()
    p.write_text(
        json.dumps(cfg.model_dump(mode="json", by_alias=True), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_schedule_state() -> dict[str, Any]:
    p = schedule_state_path()
    if not p.is_file():
        return {"lastShownAtBySceneId": {}}
    return json.loads(p.read_text(encoding="utf-8"))


def save_schedule_state(state: dict[str, Any]) -> None:
    p = schedule_state_path()
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def touch_last_shown(scene_id: str) -> None:
    st = load_schedule_state()
    m = st.setdefault("lastShownAtBySceneId", {})
    m[scene_id] = _utc_iso()
    save_schedule_state(st)


def append_wall_run(run: WallRun) -> None:
    p = wall_runs_path()
    line = json.dumps(run.model_dump(mode="json", by_alias=True), ensure_ascii=False)
    with p.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def new_wall_run_id() -> str:
    return str(uuid.uuid4())
