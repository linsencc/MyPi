#!/usr/bin/env python3
"""
Standalone demo: reach Pinterest through an HTTP(S) CONNECT proxy.

- No imports from MyPi; safe for a throwaway venv or your laptop.
- Does not touch mypi.service or the Pi production venv unless you run it there on purpose.

Usage (Windows / Linux / Pi):

  set HTTPS_PROXY=http://127.0.0.1:7890
  python demo_proxy_pinterest.py

  python demo_proxy_pinterest.py --proxy http://192.168.1.10:7890

Optional: set MYPI_PINTEREST_ACCESS_TOKEN or PINTEREST_ACCESS_TOKEN to also probe api.pinterest.com/v5/user_account (Bearer).
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import urllib.error
import urllib.request

_UA = "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"


def _proxy_from_args_and_env(explicit: str | None) -> str | None:
    p = (explicit or "").strip()
    if p:
        return p
    for key in ("MYPI_LLM_PROXY", "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        v = os.environ.get(key, "").strip()
        if v:
            return v
    return None


def _build_opener(use_proxy: bool, proxy_url: str | None) -> urllib.request.OpenerDirector:
    if not use_proxy or not proxy_url:
        return urllib.request.build_opener()
    h = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
    return urllib.request.build_opener(h)


def _request(
    opener: urllib.request.OpenerDirector,
    url: str,
    headers: dict[str, str],
    timeout: float,
) -> tuple[int, bytes]:
    """GET url; return (status, body). HTTP 4xx/5xx do not raise."""
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with opener.open(req, timeout=timeout) as resp:
            body = resp.read(200_000)
        return resp.status, body
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:200_000]


def main() -> int:
    ap = argparse.ArgumentParser(description="Demo: Pinterest HTTPS via proxy (stdlib only).")
    ap.add_argument(
        "--proxy",
        default=None,
        help="HTTP proxy URL, e.g. http://127.0.0.1:7890 (else MYPI_LLM_PROXY / HTTPS_PROXY)",
    )
    ap.add_argument(
        "--no-proxy",
        action="store_true",
        help="Force direct connection (ignore env proxy and --proxy).",
    )
    ap.add_argument("--timeout", type=float, default=20.0, help="Per-request timeout seconds.")
    args = ap.parse_args()

    proxy = None if args.no_proxy else _proxy_from_args_and_env(args.proxy)
    opener_direct = _build_opener(False, None)
    opener_via = _build_opener(True, proxy) if proxy else opener_direct

    print("proxy:", proxy or "(none, direct)")
    token = (
        os.environ.get("MYPI_PINTEREST_ACCESS_TOKEN", "").strip()
        or os.environ.get("PINTEREST_ACCESS_TOKEN", "").strip()
    )
    print("Pinterest API token:", "set" if token else "not set (www probe only)")

    targets: list[tuple[str, dict[str, str]]] = [
        (
            "https://www.pinterest.com/",
            {"User-Agent": _UA, "Accept": "text/html,*/*;q=0.8"},
        ),
    ]
    if token:
        targets.append(
            (
                "https://api.pinterest.com/v5/user_account",
                {
                    "User-Agent": _UA,
                    "Accept": "application/json",
                    "Authorization": "Bearer " + token,
                },
            )
        )

    def run_label(label: str, op: urllib.request.OpenerDirector) -> bool:
        ok_all = True
        for url, hdrs in targets:
            try:
                status, body = _request(op, url, hdrs, args.timeout)
                line = f"  [{label}] {url} -> HTTP {status}, bytes~{len(body)}"
                if "api.pinterest.com" in url and status == 200 and body:
                    try:
                        data = json.loads(body.decode("utf-8"))
                        un = data.get("username")
                        if un:
                            line += f", username={un!r}"
                    except Exception:
                        pass
                print(line)
                if status >= 500:
                    ok_all = False
            except OSError as e:
                print(f"  [{label}] {url} -> FAIL {e!r}")
                ok_all = False
            except ssl.SSLError as e:
                print(f"  [{label}] {url} -> SSL {e!r}")
                ok_all = False
            except Exception as e:
                print(f"  [{label}] {url} -> ERROR {e!r}")
                ok_all = False
        return ok_all

    print("\n--- Through configured route (proxy if set) ---")
    ok_route = run_label("route", opener_via)

    if token and proxy and not args.no_proxy:
        print("\n--- Same API URL, direct (no proxy) for comparison ---")
        try:
            status, body = _request(
                opener_direct,
                "https://api.pinterest.com/v5/user_account",
                {
                    "User-Agent": _UA,
                    "Accept": "application/json",
                    "Authorization": "Bearer " + token,
                },
                args.timeout,
            )
            print(f"  [direct] https://api.pinterest.com/v5/user_account -> HTTP {status}, bytes~{len(body)}")
        except Exception as e:
            print(f"  [direct] api user_account -> FAIL {e!r}")

    if not proxy and not args.no_proxy:
        print("\nHint: pass --proxy or set HTTPS_PROXY to test the proxy path.")

    return 0 if ok_route else 1


if __name__ == "__main__":
    raise SystemExit(main())
