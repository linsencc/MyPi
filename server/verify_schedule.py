"""Time / schedule logic checks (next_fire_time, wall/state.upcoming shape).

Run from server: PYTHONPATH=. python verify_schedule.py
"""
from __future__ import annotations

import re
import sys
from datetime import UTC, datetime, timedelta

from zoneinfo import ZoneInfo

from domain.models import Scene
from orchestrator.next_run import global_min_next, next_fire_time


def _scene_cron(weekdays: list[int], time_s: str) -> Scene:
    return Scene.model_validate(
        {
            "id": "t-scene",
            "templateId": "daily_motto",
            "enabled": True,
            "schedule": {"type": "cron_weekly", "time": time_s, "weekdays": weekdays},
        }
    )


def _scene_interval(sec: int) -> Scene:
    return Scene.model_validate(
        {
            "id": "t-int",
            "templateId": "daily_motto",
            "enabled": True,
            "schedule": {"type": "interval", "intervalSeconds": sec},
        }
    )


def main() -> int:
    fails = 0
    tz = ZoneInfo("Asia/Shanghai")

    # TC-S1: Sunday 20:00 Shanghai -> next weekday slot is Monday 10:00
    sun_evening_utc = datetime(2026, 4, 5, 12, 0, 0, tzinfo=UTC)  # CST Sun 20:00
    sc = _scene_cron([1, 2, 3, 4, 5], "10:00")
    nxt = next_fire_time(sc, None, sun_evening_utc, tz)
    expect = datetime(2026, 4, 6, 2, 0, 0, tzinfo=UTC)  # Mon 10:00 CST
    if nxt != expect:
        print("FAIL TC-S1 cron next Monday", nxt, "!=", expect)
        fails += 1
    else:
        print("OK TC-S1 cron_weekly Sun evening -> Mon 10:00 local")

    # TC-S2: Monday 09:00 Shanghai same week -> same day 10:00
    mon_9_utc = datetime(2026, 4, 6, 1, 0, 0, tzinfo=UTC)  # Mon 09:00 CST
    nxt2 = next_fire_time(sc, None, mon_9_utc, tz)
    expect2 = datetime(2026, 4, 6, 2, 0, 0, tzinfo=UTC)
    if nxt2 != expect2:
        print("FAIL TC-S2 same-day window", nxt2, "!=", expect2)
        fails += 1
    else:
        print("OK TC-S2 cron_weekly Mon 09:00 -> Mon 10:00 same day")

    # TC-S3: Monday 11:00 -> skip to Tuesday 10:00 (weekdays Mon-Fri)
    mon_11_utc = datetime(2026, 4, 6, 3, 0, 0, tzinfo=UTC)  # Mon 11:00 CST
    nxt3 = next_fire_time(sc, None, mon_11_utc, tz)
    expect3 = datetime(2026, 4, 7, 2, 0, 0, tzinfo=UTC)  # Tue 10:00 CST
    if nxt3 != expect3:
        print("FAIL TC-S3 skip to Tue", nxt3, "!=", expect3)
        fails += 1
    else:
        print("OK TC-S3 cron after slot -> next weekday")

    # TC-S4: interval no last
    si = _scene_interval(3600)
    t0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    ni = next_fire_time(si, None, t0, tz)
    if ni != t0:
        print("FAIL TC-S4 interval first fire", ni)
        fails += 1
    else:
        print("OK TC-S4 interval first fire = now")

    # TC-S5: interval with last_shown
    last = datetime(2026, 1, 1, 1, 0, 0, tzinfo=UTC)
    ni2 = next_fire_time(si, last, t0, tz)
    if ni2 != last + timedelta(seconds=3600):
        print("FAIL TC-S5 interval from last", ni2)
        fails += 1
    else:
        print("OK TC-S5 interval from last_shown")

    # TC-S6: disabled -> None
    sc_off = sc.model_copy(update={"enabled": False})
    if next_fire_time(sc_off, None, sun_evening_utc, tz) is not None:
        print("FAIL TC-S6 disabled should not fire")
        fails += 1
    else:
        print("OK TC-S6 disabled scene -> no next")

    # TC-S7: global_min_next picks earliest among two
    a = _scene_cron([1], "10:00")  # id t-scene
    b = Scene.model_validate(
        {
            "id": "other",
            "templateId": "daily_motto",
            "enabled": True,
            "schedule": {"type": "cron_weekly", "time": "09:00", "weekdays": [1]},
        }
    )
    # Monday 08:00 CST -> a fires 10:00, b fires 09:00 same day
    mon_8_utc = datetime(2026, 4, 6, 0, 0, 0, tzinfo=UTC)
    last_map: dict[str, str] = {}
    gmin = global_min_next([a, b], last_map, mon_8_utc, tz)
    exp_min = datetime(2026, 4, 6, 1, 0, 0, tzinfo=UTC)  # 09:00 CST
    if gmin != exp_min:
        print("FAIL TC-S7 global_min_next", gmin, "!=", exp_min)
        fails += 1
    else:
        print("OK TC-S7 global_min_next earliest scene")

    # TC-S10: cron with last_shown on a prior week — slot a few minutes ago must still be the next fire
    # (regression: old logic skipped cand_local <= now-1min and jumped to the next weekday)
    sc_mon = _scene_cron([1, 2, 3, 4, 5], "10:00")
    last_prev_week = datetime(2026, 3, 30, 2, 0, 0, tzinfo=UTC)  # Mon 10:00 CST prior week
    mon_1003_utc = datetime(2026, 4, 6, 2, 3, 0, tzinfo=UTC)  # Mon 10:03 CST same week
    nxt_late = next_fire_time(sc_mon, last_prev_week, mon_1003_utc, tz)
    expect_mon_slot = datetime(2026, 4, 6, 2, 0, 0, tzinfo=UTC)  # Mon 10:00 CST
    if nxt_late != expect_mon_slot:
        print("FAIL TC-S10 cron late same-day slot", nxt_late, "!=", expect_mon_slot)
        fails += 1
    else:
        print("OK TC-S10 cron_weekly last week -> same Mon 10:00 even if now past slot")

    # --- Integration: wall/state upcoming shape ---
    from app.factory import create_app

    app = create_app()
    c = app.test_client()
    r = c.get("/api/v1/wall/state")
    if r.status_code != 200:
        print("FAIL TC-S8 wall/state status", r.status_code)
        fails += 1
    else:
        ws = r.get_json()
        up = ws.get("upcoming")
        if not isinstance(up, list):
            print("FAIL TC-S8 upcoming not list")
            fails += 1
        else:
            iso_z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")
            bad = False
            for item in up:
                at = item.get("at")
                sid = item.get("sceneId")
                if not sid or not isinstance(at, str) or not iso_z.match(at):
                    bad = True
                    break
                try:
                    datetime.fromisoformat(at.replace("Z", "+00:00"))
                except ValueError:
                    bad = True
                    break
            if bad:
                print("FAIL TC-S8 upcoming item shape", up[:2])
                fails += 1
            else:
                print("OK TC-S8 wall/state upcoming[] ISO Z + sceneId", len(up), "items")

    # TC-S9: wall_alarm must allow late fire (default APScheduler grace is 1s; missed wakeups stall scenes)
    sched = app.extensions.get("scheduler")
    job = sched.get_job("wall_alarm") if sched else None
    if job is None:
        print("FAIL TC-S9 wall_alarm job missing")
        fails += 1
    elif job.misfire_grace_time is not None:
        print("FAIL TC-S9 wall_alarm misfire_grace_time", job.misfire_grace_time, "expected None")
        fails += 1
    else:
        print("OK TC-S9 wall_alarm misfire_grace_time=None")

    if fails:
        print("RESULT: FAIL", fails)
        return 1
    print("RESULT: OK verify_schedule")
    return 0


if __name__ == "__main__":
    sys.exit(main())
