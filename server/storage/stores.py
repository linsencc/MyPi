from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from domain.models import AppConfig, WallRun
from domain.scene_reconcile import default_scene_for_template
from storage.paths import config_path, schedule_state_path, wall_runs_path, output_dir

if TYPE_CHECKING:
    from renderers.registry import TemplateRegistry

_registry: TemplateRegistry | None = None
_config_lock = threading.Lock()
_schedule_lock = threading.Lock()

_MAX_WALL_RUNS = 200
_MAX_OUTPUT_DIRS = 200


def set_config_registry(reg: TemplateRegistry | None) -> None:
    global _registry
    _registry = reg


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _atomic_write_json(path: Path, data: str) -> None:
    """Write to a temp file then atomically replace the target."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    closed = False
    try:
        os.write(fd, data.encode("utf-8"))
        os.close(fd)
        closed = True
        os.replace(tmp, path)
    except BaseException:
        if not closed:
            os.close(fd)
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def default_config() -> AppConfig:
    s = default_scene_for_template("daily_motto", display_name="每日寄语")
    return AppConfig(scenes=[s])


def load_config() -> AppConfig:
    with _config_lock:
        p = config_path()
        if not p.is_file():
            cfg = default_config()
            _save_config_unlocked(cfg)
            return cfg
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raw = {}
        cfg = AppConfig.model_validate(raw)
        if _registry is not None:
            from domain.scene_reconcile import reconcile_scenes_with_templates

            cfg2, changed = reconcile_scenes_with_templates(cfg, _registry)
            if changed:
                _save_config_unlocked(cfg2)
            return cfg2
        return cfg


def _save_config_unlocked(cfg: AppConfig) -> None:
    p = config_path()
    _atomic_write_json(
        p,
        json.dumps(cfg.model_dump(mode="json", by_alias=True), ensure_ascii=False, indent=2),
    )


def save_config(cfg: AppConfig) -> None:
    with _config_lock:
        _save_config_unlocked(cfg)


def load_schedule_state() -> dict[str, Any]:
    with _schedule_lock:
        p = schedule_state_path()
        if not p.is_file():
            return {"lastShownAtBySceneId": {}}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"lastShownAtBySceneId": {}}


def save_schedule_state(state: dict[str, Any]) -> None:
    with _schedule_lock:
        p = schedule_state_path()
        _atomic_write_json(p, json.dumps(state, ensure_ascii=False, indent=2))


def touch_last_shown(scene_id: str) -> None:
    with _schedule_lock:
        p = schedule_state_path()
        if p.is_file():
            try:
                st = json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                st = {"lastShownAtBySceneId": {}}
        else:
            st = {"lastShownAtBySceneId": {}}
        m = st.setdefault("lastShownAtBySceneId", {})
        m[scene_id] = _utc_iso()
        _atomic_write_json(p, json.dumps(st, ensure_ascii=False, indent=2))


def append_wall_run(run: WallRun) -> None:
    p = wall_runs_path()
    line = json.dumps(run.model_dump(mode="json", by_alias=True), ensure_ascii=False)
    with p.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def new_wall_run_id() -> str:
    return str(uuid.uuid4())


def prune_old_data(keep: int = _MAX_WALL_RUNS) -> None:
    """Remove old wall_runs.jsonl entries and their output directories."""
    p = wall_runs_path()
    if not p.is_file():
        return
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    if len(lines) <= keep:
        return

    old_lines = lines[:-keep]
    keep_lines = lines[-keep:]

    keep_run_ids: set[str] = set()
    for line in keep_lines:
        try:
            obj = json.loads(line)
            keep_run_ids.add(obj.get("id", ""))
        except json.JSONDecodeError:
            continue

    _atomic_write_json(p, "\n".join(keep_lines) + "\n")

    out = output_dir()
    if out.is_dir():
        for child in out.iterdir():
            if child.is_dir() and child.name not in keep_run_ids:
                try:
                    import shutil
                    shutil.rmtree(child)
                except OSError:
                    pass
