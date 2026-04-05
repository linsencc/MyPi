"""One-off dev server without Werkzeug reloader (single process, stable wall_state).

Only one process should listen on 127.0.0.1:5050: duplicate Flask instances (e.g. old
terminals) make requests hit a random server and can show stale templates.
This script calls dev_port_check.ensure_dev_port_free before bind; if it exits, free
the port (netstat -ano | findstr :5050) or stop other MyPi server terminals.

threaded=True is required to allow Server-Sent Events (SSE) to work.
Rendering pipeline is protected by WallOrchestrator._display_lock.
Restart after changing templates.
"""
from app.factory import create_app
from dev_port_check import ensure_dev_port_free

_DEV_HOST = "127.0.0.1"
_DEV_PORT = 5050

if __name__ == "__main__":
    ensure_dev_port_free(_DEV_HOST, _DEV_PORT)
    app = create_app()
    app.run(host=_DEV_HOST, port=_DEV_PORT, debug=False, threaded=True)
