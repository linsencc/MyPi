#!/usr/bin/env python3
"""
Smoke-test pinscrape + HTTP proxy (same stack as MYPI_MOTTO_PINSCRAPE).

Does not import MyPi. Use a disposable venv on the Pi to avoid touching the
main mypi venv, or use the production venv after: pip install -r requirements-pinscrape.txt
and opencv-python-headless swap (see requirements-pinscrape.txt header).

  export HTTPS_PROXY=http://127.0.0.1:7890
  python3 demo_pinscrape_proxy.py

  python3 demo_pinscrape_proxy.py --keyword "watercolor mountain" --proxy http://127.0.0.1:7890
"""

from __future__ import annotations

import argparse
import contextlib
import os
import sys


def _proxies(explicit: str | None) -> dict[str, str]:
    p = (explicit or "").strip()
    if not p:
        p = (
            os.environ.get("MYPI_LLM_PROXY", "").strip()
            or os.environ.get("HTTPS_PROXY", "").strip()
            or os.environ.get("https_proxy", "").strip()
        )
    if not p:
        return {}
    return {"http": p, "https": p}


@contextlib.contextmanager
def _workdir(path: str):
    os.makedirs(path, exist_ok=True)
    prev = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)


@contextlib.contextmanager
def _proxy_env(px: dict[str, str]):
    """pinscrape warmup GET does not pass proxies=; honor proxy via env."""
    if not px:
        yield
        return
    keys = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy")
    saved = {k: os.environ.get(k) for k in keys}
    try:
        os.environ["HTTP_PROXY"] = px["http"]
        os.environ["HTTPS_PROXY"] = px["https"]
        os.environ["http_proxy"] = px["http"]
        os.environ["https_proxy"] = px["https"]
        yield
    finally:
        for k in keys:
            v = saved.get(k)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def main() -> int:
    ap = argparse.ArgumentParser(description="pinscrape + proxy smoke test")
    ap.add_argument("--proxy", default=None, help="HTTP proxy URL (else MYPI_LLM_PROXY / HTTPS_PROXY)")
    ap.add_argument("--keyword", default="anime landscape wallpaper", help="Pinterest search query")
    ap.add_argument("--page-size", type=int, default=6, help="pinscrape search page_size")
    ap.add_argument("--sleep", type=float, default=3.0, help="pinscrape sleep_time between calls")
    ap.add_argument(
        "--data-dir",
        default="/tmp/demo-pinscrape-data",
        help="cwd for pinscrape data/ epoch file",
    )
    args = ap.parse_args()

    try:
        from pinscrape import Pinterest
    except ImportError:
        print("pinscrape not installed. See server/requirements-pinscrape.txt", file=sys.stderr)
        return 2
    except Exception as exc:
        print("import pinscrape failed:", exc, file=sys.stderr)
        return 2

    px = _proxies(args.proxy)
    print("proxy:", px or "(none)")
    print("keyword:", args.keyword)

    try:
        with _workdir(args.data_dir), _proxy_env(px):
            p = Pinterest(proxies=px, sleep_time=max(1.0, float(args.sleep)))
            urls = p.search(args.keyword, max(4, min(50, int(args.page_size))))
    except Exception as exc:
        print("search failed:", exc, file=sys.stderr)
        return 1

    print("urls:", len(urls))
    for i, u in enumerate(urls[:5]):
        print(f"  [{i}]", str(u or "")[:100])
    return 0 if urls else 1


if __name__ == "__main__":
    raise SystemExit(main())
