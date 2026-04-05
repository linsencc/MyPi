from __future__ import annotations

import json
import logging
import re

from flask import Blueprint, abort, current_app, jsonify, request, send_file, Response

from domain.models import AppConfig, Scene
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
        
    if "schedule" not in raw:
        raw["schedule"] = {"type": "interval", "intervalSeconds": 3600}

    try:
        new_scene = Scene.model_validate(raw)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
        
    if any(s.id == new_scene.id for s in cfg.scenes):
        return jsonify({"error": "scene id already exists"}), 409
        
    reg = current_app.extensions["registry"]
    if not reg.get(new_scene.template_id):
        return jsonify({"error": "unknown templateId"}), 400
        
    cfg.scenes.append(new_scene)
    save_config(cfg)
    log.info(f"API: Created scene {new_scene.id}")
    _orch().wakeup()
    return jsonify(new_scene.model_dump(mode="json", by_alias=True))


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
    cfg = load_config()
    reg = current_app.extensions["registry"]
    if not reg.get(template_id):
        return jsonify({"error": "unknown templateId"}), 404

    # Find an enabled scene for this template
    scene = next((s for s in cfg.scenes if s.template_id == template_id and s.enabled), None)
    
    # If no enabled scene, find a disabled one
    if scene is None:
        scene = next((s for s in cfg.scenes if s.template_id == template_id), None)
        
    # If no scene exists at all, create a temporary one just for showing now
    if scene is None:
        from domain.scene_reconcile import default_scene_for_template
        plug = reg.get(template_id)
        dn = (plug.display_name if plug else None) or template_id
        scene = default_scene_for_template(template_id, display_name=dn)
        
        orch = _orch()
        log.info(f"API: Show-now requested for template_id={template_id}, enqueued ephemeral scene_id={scene.id}")
        orch.enqueue_ephemeral_scene(scene)
    else:
        orch = _orch()
        log.info(f"API: Show-now requested for template_id={template_id}, enqueued existing scene_id={scene.id}")
        orch.enqueue_show_now(scene.id)

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


@bp.get("/wall/events")
def wall_events():
    orch = _orch()
    def event_stream():
        q = orch.add_sse_client()
        try:
            while True:
                msg = q.get()
                yield msg
        except GeneratorExit:
            orch.remove_sse_client(q)
            
    response = Response(event_stream(), mimetype="text/event-stream")
    # Need to add headers to prevent buffering in proxies/web servers
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    return response


@bp.get("/output/<run_id>/<filename>")
def output_image(run_id: str, filename: str):
    """Serve a rendered frame from data/output so the web app can use it as <img src>."""
    from storage.paths import output_dir

    if not _RUN_ID_RE.match(run_id) or not _OUTPUT_NAME_RE.match(filename):
        abort(404)
    root = output_dir().resolve()
    p = (root / run_id / filename).resolve()
    try:
        p.relative_to(root)
    except ValueError:
        abort(404)
    if not p.is_file():
        abort(404)
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
