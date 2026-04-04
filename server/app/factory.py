from __future__ import annotations

import atexit
import logging
import os

from flask import Flask

from api.v1_routes import bp as api_v1_bp
from display.sink import DisplaySink
from orchestrator.service import WallOrchestrator
from pipeline.wall_show import WallPipeline
from renderers.registry import discover_plugins
from storage.stores import set_config_registry


def _is_werkzeug_reloader_parent() -> bool:
    """Avoid starting APScheduler in the reloader parent (would duplicate with child)."""
    return os.environ.get("WERKZEUG_RUN_MAIN") != "true" and os.environ.get("FLASK_DEBUG") == "1"


def create_app() -> Flask:
    logging.basicConfig(level=logging.INFO)
    app = Flask(__name__)

    registry = discover_plugins()
    set_config_registry(registry)
    pipeline = WallPipeline(registry, DisplaySink())
    orch = WallOrchestrator(pipeline, registry)

    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler()
    orch.bind_scheduler(scheduler)
    if not _is_werkzeug_reloader_parent():
        scheduler.start()
        atexit.register(lambda: scheduler.shutdown(wait=False))

    app.extensions["registry"] = registry
    app.extensions["pipeline"] = pipeline
    app.extensions["orchestrator"] = orch
    app.extensions["scheduler"] = scheduler

    app.register_blueprint(api_v1_bp, url_prefix="/api/v1")

    if not _is_werkzeug_reloader_parent():
        with app.app_context():
            orch.wakeup()

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", "5050"))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
