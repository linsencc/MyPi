"""Smoke verification for MyPi API (Flask test_client). Run from server: PYTHONPATH=. python verify_demo.py"""
from __future__ import annotations

import json
import sys


def main() -> int:
    from app.factory import create_app

    app = create_app()
    c = app.test_client()

    def j(r):
        if r.status_code >= 400:
            print("FAIL", r.status_code, r.data[:500])
            return None
        if not r.data:
            return None
        return r.get_json()

    fails = 0

    r = c.get("/api/v1/templates")
    t = j(r)
    tids = {x.get("templateId") for x in (t or [])}
    if not t or "daily_motto" not in tids or "schedule_stamp" not in tids:
        print("FAIL templates", r.status_code, t)
        fails += 1
    else:
        print("OK templates", len(t), "items")

    r = c.get("/api/v1/config")
    cfg = j(r)
    if not cfg or "scenes" not in cfg:
        print("FAIL config")
        fails += 1
    else:
        print("OK config", len(cfg["scenes"]), "scenes")

    r = c.get("/api/v1/scenes")
    scenes = j(r)
    if not isinstance(scenes, list):
        print("FAIL scenes list")
        fails += 1
    else:
        print("OK scenes", len(scenes))

    sid = cfg["scenes"][0]["id"] if cfg and cfg["scenes"] else None
    if not sid:
        print("FAIL no scene id")
        fails += 1
    else:
        r = c.get(f"/api/v1/scenes/{sid}")
        one = j(r)
        if not one or one.get("id") != sid:
            print("FAIL get scene")
            fails += 1
        else:
            print("OK get scene", sid)

        r = c.post(f"/api/v1/scenes/{sid}/show-now")
        sn = j(r)
        if not sn or not sn.get("ok"):
            print("FAIL show-now", r.status_code, r.data)
            fails += 1
        else:
            print("OK show-now")
            wsb = sn.get("wallState") or {}
            p0 = wsb.get("currentPreviewUrl")
            if not p0 or not str(p0).startswith("/api/v1/output/"):
                print("FAIL show-now wallState.currentPreviewUrl", p0)
                fails += 1
            else:
                print("OK show-now embeds preview URL")

        stamp_sid = next(
            (s["id"] for s in (cfg.get("scenes") or []) if s.get("templateId") == "schedule_stamp"),
            None,
        )
        if stamp_sid:
            r = c.post(f"/api/v1/scenes/{stamp_sid}/show-now")
            sn2 = j(r)
            if not sn2 or not sn2.get("ok"):
                print("FAIL schedule_stamp show-now", r.status_code, r.data[:300])
                fails += 1
            else:
                p2 = (sn2.get("wallState") or {}).get("currentPreviewUrl")
                if not p2 or "schedule_stamp" not in str(p2):
                    print("FAIL schedule_stamp preview path", p2)
                    fails += 1
                else:
                    r = c.get(p2)
                    if r.status_code != 200 or r.data[:8] != b"\x89PNG\r\n\x1a\n":
                        print("FAIL schedule_stamp PNG", r.status_code, p2)
                        fails += 1
                    else:
                        print("OK schedule_stamp show-now PNG")

        r = c.get("/api/v1/wall/state")
        ws = j(r)
        if not ws or "upcoming" not in ws:
            print("FAIL wall/state")
            fails += 1
        else:
            print("OK wall/state upcoming", len(ws["upcoming"]))
        prev = (ws or {}).get("currentPreviewUrl")
        if not prev or not str(prev).startswith("/api/v1/output/"):
            print("FAIL wall/state currentPreviewUrl", prev)
            fails += 1
        else:
            r = c.get(prev)
            if r.status_code != 200 or r.data[:8] != b"\x89PNG\r\n\x1a\n":
                print("FAIL output image", r.status_code, prev)
                fails += 1
            else:
                print("OK wall preview PNG", prev)

        r = c.get("/api/v1/wall/runs")
        runs = j(r)
        if not isinstance(runs, list) or len(runs) < 1:
            print("FAIL wall/runs expected >=1 after show-now", runs)
            fails += 1
        else:
            print("OK wall/runs", len(runs), "last ok=", runs[0].get("ok"))

        # disabled -> 400
        cfg["scenes"][0]["enabled"] = False
        r = c.put("/api/v1/config", data=json.dumps(cfg), content_type="application/json")
        if r.status_code != 200:
            print("FAIL put config disable")
            fails += 1
        r = c.post(f"/api/v1/scenes/{sid}/show-now")
        if r.status_code != 400:
            print("FAIL show-now disabled should be 400", r.status_code)
            fails += 1
        else:
            print("OK show-now disabled -> 400")

        cfg["scenes"][0]["enabled"] = True
        r = c.put("/api/v1/config", data=json.dumps(cfg), content_type="application/json")
        if r.status_code != 200:
            print("FAIL put config re-enable")
            fails += 1

    print("---")
    if fails:
        print("RESULT: FAIL", fails, "check(s)")
        return 1
    print("RESULT: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
