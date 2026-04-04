"""One-off dev server without Werkzeug reloader (single process, stable wall_state).

Only one process should listen on 127.0.0.1:5050: duplicate Flask instances (e.g. old
terminals) make requests hit a random server and can show empty CJK renders while
another instance would render correctly. Check with: netstat -ano | findstr :5050

threaded=False avoids concurrent Werkzeug workers sharing Pillow/FreeType state.
Restart after changing plugins.
"""
from app.factory import create_app

if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5050, debug=False, threaded=False)
