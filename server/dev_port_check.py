"""Fail fast if the dev API port is already taken (avoids duplicate Flask on 5050)."""

from __future__ import annotations

import sys


def ensure_dev_port_free(host: str, port: int) -> None:
    """
    On Windows, multiple dev servers can both LISTEN on the same port when SO_REUSEADDR
    is used, so clients hit a random instance (stale plugins/config). A short-lived bind
    with SO_EXCLUSIVEADDRUSE detects any existing listener on that port.
    On other OS, a normal bind without SO_REUSEADDR is enough to detect conflicts.
    """
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if sys.platform == "win32":
            excl = getattr(socket, "SO_EXCLUSIVEADDRUSE", None)
            if excl is not None:
                s.setsockopt(socket.SOL_SOCKET, excl, 1)
        s.bind((host, port))
    except OSError as e:
        print(
            f"ERROR: cannot bind {host}:{port} ({e!r}).\n"
            "Another process is already using this port (often a second MyPi server).\n"
            f"  Windows:  netstat -ano | findstr :{port}\n"
            "            taskkill /PID <pid> /F\n"
            "Then start only one of: python _dev_serve.py  or  python app/factory.py",
            file=sys.stderr,
        )
        raise SystemExit(1) from e
    finally:
        s.close()
