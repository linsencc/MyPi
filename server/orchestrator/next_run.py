from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from zoneinfo import ZoneInfo

from domain.models import QuietHoursConfig, Scene
from domain.utils import parse_iso as _parse_iso
from orchestrator.quiet_hours import defer_local_out_of_quiet


def _js_weekday(d: date) -> int:
    return (d.weekday() + 1) % 7


def next_fire_time(
    scene: Scene,
    last_shown_at_utc: datetime | None,
    now_utc: datetime,
    tz: ZoneInfo,
    quiet: QuietHoursConfig | None = None,
) -> datetime | None:
    if not scene.enabled:
        return None
    now_local = now_utc.astimezone(tz)
    sch = scene.schedule
    if sch.type == "interval":
        sec = sch.interval_seconds
        if last_shown_at_utc is None:
            nxt_local = now_utc.astimezone(tz)
        else:
            nxt_local = (last_shown_at_utc + timedelta(seconds=sec)).astimezone(tz)
        nxt_local = defer_local_out_of_quiet(nxt_local, tz, quiet)
        return nxt_local.astimezone(UTC)
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

            if last_shown_at_utc is None:
                if cand_local <= now_local - timedelta(minutes=1):
                    continue
            else:
                last_local = last_shown_at_utc.astimezone(tz)
                if cand_local <= last_local:
                    continue

            if quiet is not None and quiet.enabled:
                cand_local = defer_local_out_of_quiet(cand_local, tz, quiet)
                if last_shown_at_utc is not None:
                    last_local = last_shown_at_utc.astimezone(tz)
                    if cand_local <= last_local:
                        continue
                if last_shown_at_utc is None:
                    if cand_local <= now_local - timedelta(minutes=1):
                        continue
                if _js_weekday(cand_local.date()) not in wd_set:
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
    quiet: QuietHoursConfig | None = None,
) -> list[datetime]:
    """Calculate multiple future execution times for a scene."""
    if not scene.enabled:
        return []

    times: list[datetime] = []
    current_last = last_shown_at_utc
    max_time = now_utc + timedelta(hours=max_hours)

    for _ in range(limit):
        nxt = next_fire_time(scene, current_last, now_utc, tz, quiet)
        if not nxt:
            break
        if nxt > max_time:
            break
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
    quiet: QuietHoursConfig | None = None,
) -> datetime | None:
    best: datetime | None = None
    for sc in scenes:
        raw = last_map.get(sc.id)
        last = _parse_iso(raw) if raw else None
        nxt = next_fire_time(sc, last, now_utc, tz, quiet)
        if nxt is None:
            continue
        if best is None or nxt < best:
            best = nxt
    return best
