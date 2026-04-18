from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from zoneinfo import ZoneInfo

from domain.models import Scene
from domain.utils import parse_iso as _parse_iso


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
            return now_utc
        return last_shown_at_utc + timedelta(seconds=sec)
    if sch.type == "cron_weekly":
        wd_set = set(sch.weekdays or list(range(7)))
        parts = sch.time.split(":")
        hi, mi = int(parts[0]), int(parts[1])
        si = int(parts[2]) if len(parts) > 2 else 0
        for delta in range(0, 370):
            day = now_local.date() + timedelta(days=delta)
            if _js_weekday(day) not in wd_set:
                continue
            cand_local = datetime(day.year, day.month, day.day, hi, mi, si, tzinfo=tz)
            
            # If never shown, allow a small grace period (e.g. 1 minute)
            # so that if now_local is slightly past cand_local (e.g. due to scheduler jitter),
            # we don't immediately skip it.
            if last_shown_at_utc is None:
                if cand_local <= now_local - timedelta(minutes=1):
                    continue
            else:
                last_local = last_shown_at_utc.astimezone(tz)
                # Anchor on last_shown only: the next occurrence is the first matching slot strictly after it.
                # Do not skip slots that are a few minutes past now — late scheduler ticks must still fire.
                if cand_local <= last_local:
                    continue

            return cand_local.astimezone(UTC)
    return None


def future_fire_times(
    scene: Scene,
    last_shown_at_utc: datetime | None,
    now_utc: datetime,
    tz: ZoneInfo,
    limit: int = 10,
    max_hours: int = 24,
) -> list[datetime]:
    """Calculate multiple future execution times for a scene."""
    if not scene.enabled:
        return []
        
    times: list[datetime] = []
    current_last = last_shown_at_utc
    max_time = now_utc + timedelta(hours=max_hours)
    
    for _ in range(limit):
        nxt = next_fire_time(scene, current_last, now_utc, tz)
        if not nxt:
            break
        if nxt > max_time:
            break
        # To avoid same time returned infinitely if schedule is somehow broken
        if current_last and nxt <= current_last:
            break
        times.append(nxt)
        current_last = nxt
        
    return times


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
