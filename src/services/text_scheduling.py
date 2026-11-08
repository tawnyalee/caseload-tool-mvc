# src/services/text_scheduling.py
"""Picks when a text should be scheduled to arrive, in the student's own
time zone. Mongoose can only schedule texts (no immediate send) and
schedules in the student's time zone, so the real Mongoose TextSender will
call next_send_time() for each student and enter the result.

The developer's rule (2026-10-13): never text a student before 9 AM or
after 9 PM their time. This aims inside a narrower 10 AM - 8 PM window -
an hour of buffer on each side - because the roster's time zone labels are
ambiguous: "EST"/"PST" don't say whether daylight saving applies, and
"MST" could be Arizona (no daylight saving) or Denver. Each of those is at
most an hour off, so a time inside 10-8 is inside 9-9 whichever is meant.

  - inside the window now -> a few minutes from now (Mongoose likely
    needs a little lead time)
  - before 10 AM their time -> 10 AM today
  - 8 PM or later their time -> 10 AM tomorrow
  - no time zone on record -> not scheduled at all; the student is
    skipped and logged for manual handling (what Mongoose does with a
    contact that has no zone is unknown, and guessing wrong could mean a
    text in the middle of the night)

Pure functions with `now` passed in, so every case is unit-testable
without waiting for a real clock.
"""
from datetime import datetime, time, timedelta, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo

WINDOW_START = time(10, 0)
WINDOW_END = time(20, 0)  # exclusive - 8:00 PM itself rolls to tomorrow
LEAD_TIME = timedelta(minutes=10)
ROUND_TO_MINUTES = 5

# Roster labels -> real (daylight-saving-aware) zones. Daylight and
# standard spellings map to the same place on purpose; see the module
# docstring for why the ambiguity is safe.
_ZONES = {
    "EST": "America/New_York", "EDT": "America/New_York", "ET": "America/New_York",
    "CST": "America/Chicago", "CDT": "America/Chicago", "CT": "America/Chicago",
    "MST": "America/Denver", "MDT": "America/Denver", "MT": "America/Denver",
    "PST": "America/Los_Angeles", "PDT": "America/Los_Angeles", "PT": "America/Los_Angeles",
    "AKST": "America/Anchorage", "AKDT": "America/Anchorage",
    "HST": "Pacific/Honolulu",
}


class NoTimeZoneError(ValueError):
    """The student has no usable time zone - text them manually."""


def student_zone(label: str) -> ZoneInfo:
    key = (label or "").strip().upper()
    if not key:
        raise NoTimeZoneError("No time zone on record - text this student manually.")
    if key not in _ZONES:
        raise NoTimeZoneError(f"Unrecognized time zone {label!r} - text this student manually.")
    return ZoneInfo(_ZONES[key])


def _round_up(moment: datetime) -> datetime:
    """Up to the next ROUND_TO_MINUTES boundary (seconds dropped)."""
    moment = moment.replace(second=0, microsecond=0)
    extra = -moment.minute % ROUND_TO_MINUTES
    return moment + timedelta(minutes=extra)


def next_send_time(timezone_label: str, now: Optional[datetime] = None) -> datetime:
    """The time to schedule a text for, as a timezone-aware datetime in the
    student's zone. `now` must be timezone-aware (defaults to the real
    current time). Raises NoTimeZoneError if the student has no usable zone."""
    zone = student_zone(timezone_label)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    candidate = _round_up(now.astimezone(zone) + LEAD_TIME)
    today_start = datetime.combine(candidate.date(), WINDOW_START, tzinfo=zone)
    today_end = datetime.combine(candidate.date(), WINDOW_END, tzinfo=zone)

    if candidate < today_start:
        return today_start
    if candidate >= today_end:
        return datetime.combine(candidate.date() + timedelta(days=1), WINDOW_START, tzinfo=zone)
    return candidate


SHARED_SEARCH_DAYS = 3


def in_window(moment: datetime) -> bool:
    """True if `moment` (already in a student's zone) is inside 10 AM-8 PM."""
    return WINDOW_START <= moment.time() < WINDOW_END


def shared_send_time(timezone_labels: List[str], now: Optional[datetime] = None) -> datetime:
    """One time for a message going to several students (developer,
    2026-11-08: one Mongoose message per class), inside every student's own
    10 AM-8 PM window: the earliest such time from now + LEAD_TIME, on a
    ROUND_TO_MINUTES boundary. For one student it's next_send_time().

    US zones from Hawaii to Eastern overlap for five hours every day (10 AM
    Hawaii to 8 PM Eastern), so a time is always found for them. Raises
    NoTimeZoneError if a label is unusable, and ValueError if no shared time
    exists, so the caller can split the message up."""
    zones = [student_zone(label) for label in timezone_labels]
    if not zones:
        raise ValueError("No students to schedule for")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    candidate = _round_up(now.astimezone(timezone.utc) + LEAD_TIME)
    last = candidate + timedelta(days=SHARED_SEARCH_DAYS)
    while candidate <= last:
        if all(in_window(candidate.astimezone(zone)) for zone in zones):
            return candidate.astimezone(zones[0])
        candidate += timedelta(minutes=ROUND_TO_MINUTES)
    raise ValueError("No time is inside 10 AM-8 PM for every one of these students")
