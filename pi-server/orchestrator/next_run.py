from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from zoneinfo import ZoneInfo

from domain.models import Scene


def _parse_iso(s: str) -> datetime:
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def _js_weekday(d: date) -> int:
    return (d.weekday() + 1) % 7


def next_fire_time(
    scene: Scene,
    last_shown_at_utc: datetime | None,
    now_utc: datetime,
    tz: ZoneInfo,
) -> datetime | None:
    if not scene.enabled:
        return None
    now_local = now_utc.astimezone(tz)
    sch = scene.schedule
    if sch.type == "interval":
        sec = sch.interval_seconds
        if last_shown_at_utc is None:
            return now_utc + timedelta(seconds=sec)
        return last_shown_at_utc + timedelta(seconds=sec)
    if sch.type == "cron_weekly":
        wd_set = set(sch.weekdays or list(range(7)))
        h, m = sch.time.split(":")
        hi, mi = int(h), int(m)
        for delta in range(0, 370):
            day = now_local.date() + timedelta(days=delta)
            if _js_weekday(day) not in wd_set:
                continue
            cand_local = datetime(day.year, day.month, day.day, hi, mi, tzinfo=tz)
            if cand_local <= now_local:
                continue
            return cand_local.astimezone(UTC)
    return None


def global_min_next(
    scenes: list[Scene],
    last_map: dict[str, str],
    now_utc: datetime,
    tz: ZoneInfo,
) -> datetime | None:
    best: datetime | None = None
    for sc in scenes:
        raw = last_map.get(sc.id)
        last = _parse_iso(raw) if raw else None
        nxt = next_fire_time(sc, last, now_utc, tz)
        if nxt is None:
            continue
        if best is None or nxt < best:
            best = nxt
    return best
