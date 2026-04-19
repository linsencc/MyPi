from __future__ import annotations

from datetime import datetime, time, timedelta

from zoneinfo import ZoneInfo

from domain.models import QuietHoursConfig


def _parse_hms(s: str) -> tuple[int, int, int]:
    parts = s.strip().split(":")
    hi, mi = int(parts[0]), int(parts[1])
    si = int(parts[2]) if len(parts) > 2 else 0
    return hi, mi, si


def local_datetime_in_quiet(local_dt: datetime, start_s: str, end_s: str) -> bool:
    hi, mi, si = _parse_hms(start_s)
    hj, mj, sj = _parse_hms(end_s)
    t_plain = time(
        local_dt.hour, local_dt.minute, local_dt.second, local_dt.microsecond
    )
    st = time(hi, mi, si)
    et = time(hj, mj, sj)
    if st < et:
        return st <= t_plain < et
    if st > et:
        return t_plain >= st or t_plain < et
    return False


def exit_quiet_local(local_dt: datetime, tz: ZoneInfo, start_s: str, end_s: str) -> datetime:
    if not local_datetime_in_quiet(local_dt, start_s, end_s):
        return local_dt
    hi, mi, si = _parse_hms(start_s)
    hj, mj, sj = _parse_hms(end_s)
    st = time(hi, mi, si)
    et = time(hj, mj, sj)
    d = local_dt.date()
    if st < et:
        return datetime.combine(d, et, tzinfo=tz)
    t_plain = time(local_dt.hour, local_dt.minute, local_dt.second, local_dt.microsecond)
    if t_plain >= st:
        return datetime.combine(d + timedelta(days=1), et, tzinfo=tz)
    return datetime.combine(d, et, tzinfo=tz)


def defer_local_out_of_quiet(
    local_dt: datetime, tz: ZoneInfo, quiet: QuietHoursConfig | None
) -> datetime:
    if quiet is None or not quiet.enabled:
        return local_dt
    s, e = quiet.start_local, quiet.end_local
    out = local_dt
    for _ in range(400):
        if not local_datetime_in_quiet(out, s, e):
            return out
        out = exit_quiet_local(out, tz, s, e)
    return out
