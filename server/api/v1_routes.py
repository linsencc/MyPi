from __future__ import annotations

import json
import logging
import re
from typing import Any

from flask import Blueprint, current_app, jsonify, request, send_file
from pydantic import ValidationError

from api.validation_errors import scene_validation_error_response
from domain.models import AppConfig, Scene
from renderers.templates.ui_params import (
    merge_incoming_template_params,
    scene_template_params_after_model,
)
from storage.stores import load_config, save_config

log = logging.getLogger(__name__)
bp = Blueprint("v1", __name__)

_RUN_ID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_OUTPUT_NAME_RE = re.compile(r"^[a-zA-Z0-9_.-]+$")


def _orch():
    return current_app.extensions["orchestrator"]


def _param_schema_for_template(template_id: str) -> list[dict[str, Any]]:
    reg = current_app.extensions["registry"]
    plug = reg.get(template_id)
    if not plug:
        return []
    return list(getattr(type(plug), "param_schema", []) or [])


@bp.get("/config")
def get_config():
    cfg = load_config()
    return jsonify(cfg.model_dump(mode="json", by_alias=True))


@bp.put("/config")
def put_config():
    raw = request.get_json(force=True, silent=False)
    cfg = AppConfig.model_validate(raw)
    save_config(cfg)
    log.info("API: Updated global configuration")
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
    import uuid
    cfg = load_config()
    raw = request.get_json(force=True, silent=False)
    
    if "id" not in raw or not raw["id"]:
        safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in raw.get("templateId", "unknown"))
        raw["id"] = f"scene-{safe}-{str(uuid.uuid4())[:8]}"
        
    if "schedule" not in raw:
        raw["schedule"] = {"type": "interval", "intervalSeconds": 3600}

    try:
        new_scene = Scene.model_validate(raw)
    except ValidationError as e:
        return jsonify(scene_validation_error_response(e)), 400
        
    if any(s.id == new_scene.id for s in cfg.scenes):
        return jsonify({"error": "scene id already exists"}), 409
        
    reg = current_app.extensions["registry"]
    if not reg.get(new_scene.template_id):
        return jsonify({"error": "unknown templateId"}), 400

    schema = _param_schema_for_template(new_scene.template_id)
    norm, terr = scene_template_params_after_model(schema, new_scene.template_params)
    if terr:
        return jsonify({"error": f"Invalid templateParams: {terr}"}), 400
    new_scene = new_scene.model_copy(update={"template_params": norm})

    cfg.scenes.append(new_scene)
    save_config(cfg)
    log.info(f"API: Created scene {new_scene.id}")
    _orch().wakeup()
    return jsonify(new_scene.model_dump(mode="json", by_alias=True)), 201


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
    try:
        new = Scene.model_validate(raw)
    except ValidationError as e:
        return jsonify(scene_validation_error_response(e)), 400
    if new.id != scene_id:
        return jsonify({"error": "id mismatch"}), 400
    idx = next((i for i, s in enumerate(cfg.scenes) if s.id == scene_id), None)
    if idx is None:
        return jsonify({"error": "not found"}), 404
    if new.template_id != cfg.scenes[idx].template_id:
        return jsonify({"error": "templateId is fixed for this card"}), 400

    reg = current_app.extensions["registry"]
    schema = _param_schema_for_template(new.template_id)
    norm, terr = scene_template_params_after_model(schema, new.template_params)
    if terr:
        return jsonify({"error": f"Invalid templateParams: {terr}"}), 400
    new = new.model_copy(update={"template_params": norm})

    cfg.scenes[idx] = new
    save_config(cfg)
    log.info(f"API: Updated scene {new.id}")
    _orch().wakeup()
    return jsonify(new.model_dump(mode="json", by_alias=True))


@bp.delete("/scenes/<scene_id>")
def delete_scene(scene_id: str):
    cfg = load_config()
    idx = next((i for i, s in enumerate(cfg.scenes) if s.id == scene_id), None)
    if idx is None:
        return jsonify({"error": "not found"}), 404
        
    cfg.scenes.pop(idx)
    save_config(cfg)
    log.info(f"API: Deleted scene {scene_id}")
    _orch().wakeup()
    return "", 204


@bp.post("/templates/<template_id>/show-now")
def show_now_template(template_id: str):
    from domain.scene_reconcile import allocate_scene_id, default_scene_for_template

    cfg = load_config()
    reg = current_app.extensions["registry"]
    plug = reg.get(template_id)
    if not plug:
        return jsonify({"error": "unknown templateId"}), 404

    body = request.get_json(silent=True)
    params_override: dict[str, Any] | None = None
    if isinstance(body, dict) and "templateParams" in body:
        raw_tp = body.get("templateParams")
        if raw_tp is None:
            params_override = None
        elif not isinstance(raw_tp, dict):
            return jsonify({"error": "templateParams must be an object"}), 400
        else:
            params_override = raw_tp

    base = next((s for s in cfg.scenes if s.template_id == template_id and s.enabled), None)
    if base is None:
        base = next((s for s in cfg.scenes if s.template_id == template_id), None)

    orch = _orch()

    if params_override is not None:
        if base is None:
            dn = plug.display_name or template_id
            base = default_scene_for_template(template_id, display_name=dn)
        schema_fields = _param_schema_for_template(template_id)
        merged = merge_incoming_template_params(
            schema_fields, base.template_params or {}, params_override
        )
        ephemeral = base.model_copy(
            update={
                "id": allocate_scene_id(template_id),
                "template_params": merged,
                "enabled": True,
            }
        )
        log.info(
            "API: Show-now with templateParams template_id=%s ephemeral_id=%s",
            template_id,
            ephemeral.id,
        )
        orch.enqueue_ephemeral_scene(ephemeral)
    elif base is None:
        dn = plug.display_name or template_id
        scene = default_scene_for_template(template_id, display_name=dn)
        log.info(
            "API: Show-now requested for template_id=%s, enqueued ephemeral scene_id=%s",
            template_id,
            scene.id,
        )
        orch.enqueue_ephemeral_scene(scene)
    else:
        log.info(
            "API: Show-now requested for template_id=%s, enqueued existing scene_id=%s",
            template_id,
            base.id,
        )
        orch.enqueue_show_now(base.id)

    return jsonify(
        {
            "ok": True,
            "wallState": orch.wall_state.model_dump(mode="json", by_alias=True),
        }
    )

@bp.post("/scenes/<scene_id>/show-now")
def show_now(scene_id: str):
    cfg = load_config()
    scene = next((s for s in cfg.scenes if s.id == scene_id), None)
    if scene is None:
        return jsonify({"error": "not found"}), 404
    if not scene.enabled:
        return jsonify({"error": "scene disabled"}), 400
    orch = _orch()
    log.info(f"API: Show-now requested for scene_id={scene_id}")
    orch.enqueue_show_now(scene_id)
    return jsonify(
        {
            "ok": True,
            "wallState": orch.wall_state.model_dump(mode="json", by_alias=True),
        }
    )


@bp.get("/system/logs")
def system_logs():
    from app.log_setup import memory_handler
    logs = memory_handler.get_recent_logs()
    return jsonify(logs)

@bp.get("/wall/state")
def wall_state():
    st = _orch().wall_state
    return jsonify(st.model_dump(mode="json", by_alias=True))



@bp.get("/output/<run_id>/<filename>")
def output_image(run_id: str, filename: str):
    """Serve a rendered frame from data/output so the web app can use it as <img src>."""
    from storage.paths import output_dir

    if not _RUN_ID_RE.match(run_id) or not _OUTPUT_NAME_RE.match(filename):
        return jsonify({"error": "not found"}), 404
    root = output_dir().resolve()
    p = (root / run_id / filename).resolve()
    try:
        p.relative_to(root)
    except ValueError:
        return jsonify({"error": "not found"}), 404
    if not p.is_file():
        return jsonify({"error": "not found"}), 404
    return send_file(p, mimetype="image/png")


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
