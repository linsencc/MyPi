#!/usr/bin/env python3
"""Print HTTP status for a few v5 endpoints (token from env). For Pi / local smoke checks."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _pinterest_access_token() -> str:
    return (
        os.environ.get("MYPI_PINTEREST_ACCESS_TOKEN", "").strip()
        or os.environ.get("PINTEREST_ACCESS_TOKEN", "").strip()
    )


def main() -> int:
    token = _pinterest_access_token()
    if not token:
        print("MYPI_PINTEREST_ACCESS_TOKEN / PINTEREST_ACCESS_TOKEN: MISSING")
        return 2
    paths = [
        "/v5/user_account",
        "/v5/boards?page_size=3",
        "/v5/search/partner/pins?term=nature&country_code=US&limit=2",
    ]
    for path in paths:
        req = urllib.request.Request(
            "https://api.pinterest.com" + path,
            headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                raw = resp.read()[:500]
                print(path, "-> HTTP", resp.status)
                try:
                    data = json.loads(raw.decode())
                    if path.startswith("/v5/user_account"):
                        print("  username:", data.get("username"))
                        print("  account_type:", data.get("account_type"))
                except Exception:
                    pass
        except urllib.error.HTTPError as e:
            body = e.read()[:500].decode("utf-8", "replace")
            print(path, "-> HTTP", e.code, body.replace("\n", " ")[:400])
    print(
        "\nConsole 'limited scopes' often lists: pins:read, boards:read, "
        "user_accounts:read, ads:read, catalogs:read — infer from 200 vs 401/403 above."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
