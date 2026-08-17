"""
Single source of truth for "what time is it".

Every timestamp the system records (audit logs, check-ins, consultations,
prescriptions) goes through here so it is stamped in the clinic's timezone
rather than whatever the host happens to be set to. A server running in UTC
was writing UTC wall-clock strings into the audit log, which is why the times
shown in the UI were 5h30m behind the actual action.

Timestamps are persisted as ISO-8601 strings *with* the UTC offset
(e.g. 2026-08-11T14:32:07+05:30) so they stay unambiguous even if the clinic
timezone setting is later changed. Display formatting is left to the UI.
"""
import os
from datetime import date, datetime, timedelta, timezone
from typing import Optional

CLINIC_TIMEZONE = os.getenv("CLINIC_TIMEZONE", "Asia/Kolkata")

# IST fallback for hosts with no tz database installed (bare Windows images
# without `tzdata`). Only used when the named zone cannot be resolved.
_FALLBACK_TZ = timezone(timedelta(hours=5, minutes=30), "IST")


def _resolve_tz():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(CLINIC_TIMEZONE)
    except Exception:
        return _FALLBACK_TZ


TZ = _resolve_tz()


def now() -> datetime:
    """Current time as a timezone-aware datetime in the clinic timezone."""
    return datetime.now(TZ)


def today() -> date:
    """Today's date in the clinic timezone (not the host's)."""
    return now().date()


def now_iso() -> str:
    """Current time as an ISO-8601 string with offset — the storage format."""
    return now().isoformat(timespec="seconds")


def parse(value: Optional[str]) -> Optional[datetime]:
    """
    Parse a stored timestamp back into a clinic-local aware datetime.

    Accepts the ISO-8601 storage format, and also the two legacy formats that
    already exist in deployed databases so historical rows still resolve:
      * "Jun 13, 2026 05:30 PM"  (old audit log format)
      * "05:30 PM"               (old checkin_time — assumed to be today)
    Returns None when the value cannot be understood.
    """
    if not value:
        return None
    raw = value.strip()

    try:
        parsed = datetime.fromisoformat(raw)
        return parsed.astimezone(TZ) if parsed.tzinfo else parsed.replace(tzinfo=TZ)
    except ValueError:
        pass

    for fmt in ("%b %d, %Y %I:%M %p", "%b %d, %Y %I:%M:%S %p", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=TZ)
        except ValueError:
            continue

    # Time-only legacy value — anchor it to today so it is still bucketable.
    for fmt in ("%I:%M %p", "%H:%M"):
        try:
            t = datetime.strptime(raw, fmt).time()
            return datetime.combine(today(), t, tzinfo=TZ)
        except ValueError:
            continue

    return None


def parse_date(value: Optional[str]) -> Optional[date]:
    """Date portion of a stored timestamp, in clinic-local terms."""
    dt = parse(value)
    return dt.date() if dt else None


def fmt_clock(dt: Optional[datetime] = None) -> str:
    """12-hour clock label, e.g. '02:45 PM'."""
    return (dt or now()).strftime("%I:%M %p")


def minutes_between(start: Optional[str], end: Optional[str]) -> Optional[float]:
    """
    Elapsed minutes between two stored timestamps, or None when either side is
    missing or the ordering is impossible (clock skew, back-dated edits).
    """
    a, b = parse(start), parse(end)
    if not a or not b:
        return None
    delta = (b - a).total_seconds() / 60.0
    return delta if delta >= 0 else None
