"""Smoke verification for MyPi API (Flask test_client). Run from server: PYTHONPATH=. python verify_demo.py"""
from __future__ import annotations

import json
import os
import sys
import time


def _wait_wall_preview(c, j, timeout_s: float = 45.0, url_contains: str | None = None):
    """show-now returns before the async drain finishes; poll wall/state for output URL."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        r = c.get("/api/v1/wall/state")
        ws = j(r)
        p = (ws or {}).get("currentPreviewUrl")
        if not p or not str(p).startswith("/api/v1/output/"):
            time.sleep(0.05)
            continue
        if url_contains is not None and url_contains not in str(p):
            time.sleep(0.05)
            continue
        return ws
    return None


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
    if not t or "misc_gallery" not in tids or "ai_motto" not in tids:
        print("FAIL templates", r.status_code, t)
        fails += 1
    else:
        print("OK templates", len(t), "items")
        schema_ok = True
        for item in t:
            tid = item.get("templateId")
            ps = item.get("paramSchema")
            if tid in ("ai_motto", "misc_gallery"):
                if not isinstance(ps, list) or not ps:
                    print("FAIL templates paramSchema", tid, ps)
                    schema_ok = False
                elif tid == "misc_gallery":
                    if ps[0].get("key") != "text" or ps[0].get("type") != "string":
                        print("FAIL templates paramSchema", tid, ps)
                        schema_ok = False
                else:
                    keys_types = {x.get("key"): x.get("type") for x in ps if isinstance(x, dict)}
                    if (
                        keys_types.get("text") != "string"
                        or keys_types.get("with_image") != "boolean"
                    ):
                        print("FAIL templates paramSchema", tid, ps)
                        schema_ok = False
        if schema_ok:
            print("OK templates paramSchema")
        else:
            fails += 1

    r = c.get("/api/v1/config")
    cfg = j(r)
    if not cfg or "scenes" not in cfg:
        print("FAIL config")
        fails += 1
    else:
        print("OK config", len(cfg["scenes"]), "scenes")

    if cfg and not cfg.get("scenes"):
        r = c.post(
            "/api/v1/scenes",
            data=json.dumps({"templateId": "misc_gallery", "name": "杂锦摘句"}),
            content_type="application/json",
        )
        if r.status_code != 201:
            print("FAIL seed scene for smoke test", r.status_code, r.data[:400])
            fails += 1
        else:
            r = c.get("/api/v1/config")
            cfg = j(r)
            print("OK seeded scene, now", len(cfg.get("scenes") or []), "scenes")

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

            # Unknown templateParams keys must be stripped on PUT (framework sanitize).
            one_put = dict(one)
            one_put["templateParams"] = {"text": "", "garbageKey": 1}
            r = c.put(
                f"/api/v1/scenes/{sid}",
                data=json.dumps(one_put),
                content_type="application/json",
            )
            put_body = j(r)
            if r.status_code != 200 or not put_body:
                print("FAIL scene put sanitize", r.status_code, getattr(r, "data", b"")[:300])
                fails += 1
            else:
                tps = put_body.get("templateParams") or {}
                if "garbageKey" in tps:
                    print("FAIL scene put should strip unknown keys", tps)
                    fails += 1
                elif "text" in tps:
                    print("FAIL scene put optional empty text should be omitted", tps)
                    fails += 1
                else:
                    print("OK scene put templateParams sanitized")

        r = c.post(f"/api/v1/scenes/{sid}/show-now")
        sn = j(r)
        if not sn or not sn.get("ok"):
            print("FAIL show-now", r.status_code, r.data)
            fails += 1
        else:
            print("OK show-now")
            wsb = _wait_wall_preview(c, j)
            p0 = (wsb or {}).get("currentPreviewUrl")
            if not p0 or not str(p0).startswith("/api/v1/output/"):
                print("FAIL show-now wallState.currentPreviewUrl after wait", p0)
                fails += 1
            else:
                print("OK show-now embeds preview URL")

            r = c.post(
                "/api/v1/templates/misc_gallery/show-now",
                data=json.dumps({"templateParams": {"text": "verify_demo_param_override"}}),
                content_type="application/json",
            )
            tp_sn = j(r)
            if not tp_sn or not tp_sn.get("ok"):
                print("FAIL template show-now with templateParams", r.status_code, r.data[:200])
                fails += 1
            else:
                print("OK template show-now templateParams")
                _wait_wall_preview(c, j, timeout_s=45.0)

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

        delay_ms = os.environ.get("MYPI_EINK_SHOW_DELAY_MS", "").strip()
        alt_sid = next(
            (s["id"] for s in (cfg.get("scenes") or []) if s.get("id") != sid),
            None,
        )
        if delay_ms and alt_sid:
            print("--- queue smoke (MYPI_EINK_SHOW_DELAY_MS=%s)" % delay_ms)
            r = c.post(f"/api/v1/scenes/{sid}/show-now")
            snq1 = j(r)
            if not snq1 or not snq1.get("ok"):
                print("FAIL queue smoke first show-now")
                fails += 1
            else:
                r2 = c.post(f"/api/v1/scenes/{alt_sid}/show-now")
                snq = j(r2)
                if not snq or not snq.get("ok"):
                    print("FAIL queue smoke second show-now", r2.status_code)
                    fails += 1
                else:
                    wsq = snq.get("wallState") or {}
                    q = wsq.get("queuedDisplaySceneIds") or []
                    active = wsq.get("displayActiveSceneId")
                    if alt_sid in q or active == sid:
                        print("OK queue smoke (active=%r queued=%r)" % (active, q))
                    else:
                        print(
                            "FAIL queue smoke expected alt in queue or sid active",
                            "active=",
                            active,
                            "queued=",
                            q,
                        )
                        fails += 1

    print("---")
    if fails:
        print("RESULT: FAIL", fails, "check(s)")
        return 1
    print("RESULT: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
