from __future__ import annotations

import json

from flask import Blueprint, current_app, jsonify, request

from domain.models import AppConfig, Scene
from storage.stores import load_config, save_config

bp = Blueprint("v1", __name__)


def _orch():
    return current_app.extensions["orchestrator"]


@bp.get("/config")
def get_config():
    cfg = load_config()
    return jsonify(cfg.model_dump(mode="json", by_alias=True))


@bp.put("/config")
def put_config():
    raw = request.get_json(force=True, silent=False)
    cfg = AppConfig.model_validate(raw)
    save_config(cfg)
    _orch().wakeup()
    return jsonify(cfg.model_dump(mode="json", by_alias=True))


@bp.get("/templates")
def get_templates():
    reg = current_app.extensions["registry"]
    return jsonify(reg.all_metadata())


@bp.get("/scenes")
def list_scenes():
    cfg = load_config()
    return jsonify([s.model_dump(mode="json", by_alias=True) for s in cfg.scenes])


@bp.post("/scenes")
def create_scene():
    return (
        jsonify(
            {
                "error": "Scenes are plugin-driven: one row per installed template. Add a renderer plugin and restart the server."
            }
        ),
        409,
    )


@bp.get("/scenes/<scene_id>")
def get_scene(scene_id: str):
    cfg = load_config()
    for s in cfg.scenes:
        if s.id == scene_id:
            return jsonify(s.model_dump(mode="json", by_alias=True))
    return jsonify({"error": "not found"}), 404


@bp.put("/scenes/<scene_id>")
def put_scene(scene_id: str):
    cfg = load_config()
    raw = request.get_json(force=True, silent=False)
    new = Scene.model_validate(raw)
    if new.id != scene_id:
        return jsonify({"error": "id mismatch"}), 400
    idx = next((i for i, s in enumerate(cfg.scenes) if s.id == scene_id), None)
    if idx is None:
        return jsonify({"error": "not found"}), 404
    if new.template_id != cfg.scenes[idx].template_id:
        return jsonify({"error": "templateId is fixed for this card"}), 400
    cfg.scenes[idx] = new
    save_config(cfg)
    _orch().wakeup()
    return jsonify(new.model_dump(mode="json", by_alias=True))


@bp.delete("/scenes/<scene_id>")
def delete_scene(scene_id: str):
    cfg = load_config()
    if not any(s.id == scene_id for s in cfg.scenes):
        return jsonify({"error": "not found"}), 404
    return (
        jsonify(
            {"error": "Cannot delete plugin cards; remove the renderer plugin and restart to drop its scene."}
        ),
        400,
    )


@bp.post("/scenes/<scene_id>/show-now")
def show_now(scene_id: str):
    cfg = load_config()
    scene = next((s for s in cfg.scenes if s.id == scene_id), None)
    if scene is None:
        return jsonify({"error": "not found"}), 404
    if not scene.enabled:
        return jsonify({"error": "scene disabled"}), 400
    _orch().enqueue_show_now(scene_id)
    return jsonify({"ok": True})


@bp.get("/wall/state")
def wall_state():
    st = _orch().wall_state
    return jsonify(st.model_dump(mode="json", by_alias=True))


@bp.get("/wall/runs")
def wall_runs():
    from storage.paths import wall_runs_path

    p = wall_runs_path()
    if not p.is_file():
        return jsonify([])
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    tail = lines[-50:]
    out = []
    for line in tail:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return jsonify(out[::-1])
