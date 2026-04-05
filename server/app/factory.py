from __future__ import annotations

import atexit
import logging
import os

from flask import Flask

from api.v1_routes import bp as api_v1_bp
from display.sink import DisplaySink
from orchestrator.service import WallOrchestrator
from pipeline.wall_show import WallPipeline
from renderers.registry import discover_templates
from storage.stores import set_config_registry


def _is_werkzeug_reloader_parent() -> bool:
    """Avoid starting APScheduler in the reloader parent (would duplicate with child)."""
    return os.environ.get("WERKZEUG_RUN_MAIN") != "true" and os.environ.get("FLASK_DEBUG") == "1"


def create_app() -> Flask:
    from app.log_setup import memory_handler
    
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    # Basic config for console
    logging.basicConfig(level=logging.INFO, format=fmt, datefmt=datefmt)
    
    # Configure and add memory handler if not already added
    if memory_handler not in logging.getLogger().handlers:
        formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)
        memory_handler.setFormatter(formatter)
        memory_handler.setLevel(logging.INFO)
        logging.getLogger().addHandler(memory_handler)

    app = Flask(__name__)

    registry = discover_templates()
    set_config_registry(registry)
    pipeline = WallPipeline(registry, DisplaySink())
    orch = WallOrchestrator(pipeline, registry)
    
    # Hook memory handler to orchestrator's SSE
    memory_handler.on_log = lambda entry: orch._broadcast_event("system_log", entry)

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
    port = int(os.environ.get("PORT", "5050"))
    host = os.environ.get("MYPI_BIND", "0.0.0.0")
    debug = os.environ.get("FLASK_DEBUG") == "1"
    # Stat reloader re-executes this module; a pre-bind would see the child already on the port.
    if (
        not debug
        and os.environ.get("MYPI_SKIP_PORT_CHECK", "").strip() not in ("1", "true", "yes")
    ):
        from dev_port_check import ensure_dev_port_free

        ensure_dev_port_free(host, port)
    app = create_app()
    app.run(host=host, port=port, debug=debug)
