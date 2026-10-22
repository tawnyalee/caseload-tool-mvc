from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from src.services.text_scheduling import NoTimeZoneError, next_send_time

CHICAGO = ZoneInfo("America/Chicago")


def _at(zone, *args):
    return datetime(*args, tzinfo=zone)


def test_inside_the_window_schedules_a_few_minutes_from_now_rounded_up():
    now = _at(CHICAGO, 2026, 10, 22, 14, 3)  # 2:03 PM Central
    assert next_send_time("CST", now) == _at(CHICAGO, 2026, 10, 22, 14, 15)  # +10 min, rounded to :15


def test_before_10am_their_time_waits_until_10am_today():
    now = _at(CHICAGO, 2026, 10, 22, 7, 30)
    assert next_send_time("CST", now) == _at(CHICAGO, 2026, 10, 22, 10, 0)


def test_8pm_or_later_their_time_waits_until_10am_tomorrow():
    now = _at(CHICAGO, 2026, 10, 22, 19, 55)  # +10 min lead lands past 8 PM
    assert next_send_time("CST", now) == _at(CHICAGO, 2026, 10, 23, 10, 0)


def test_uses_the_students_zone_not_the_professors():
    # 11:00 AM in Chicago is 6:00 AM in Hawaii (no daylight saving there).
    now = _at(CHICAGO, 2026, 10, 22, 11, 0)
    result = next_send_time("HST", now)
    assert result == _at(ZoneInfo("Pacific/Honolulu"), 2026, 10, 22, 10, 0)


def test_late_evening_east_coast_is_still_afternoon_for_a_west_coast_student():
    now = _at(ZoneInfo("America/New_York"), 2026, 10, 22, 21, 0)  # 9 PM Eastern
    result = next_send_time("PST", now)
    assert result == _at(ZoneInfo("America/Los_Angeles"), 2026, 10, 22, 18, 10)


@pytest.mark.parametrize("label", ["", "   ", None])
def test_missing_time_zone_is_not_scheduled(label):
    with pytest.raises(NoTimeZoneError, match="text this student manually"):
        next_send_time(label, _at(CHICAGO, 2026, 10, 22, 12, 0))


def test_unrecognized_time_zone_is_not_scheduled():
    with pytest.raises(NoTimeZoneError, match="Unrecognized time zone 'GMT'"):
        next_send_time("GMT", _at(CHICAGO, 2026, 10, 22, 12, 0))


def test_labels_are_case_and_space_insensitive():
    now = _at(CHICAGO, 2026, 10, 22, 12, 0)
    assert next_send_time(" cst ", now) == next_send_time("CST", now)


def test_naive_now_is_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        next_send_time("CST", datetime(2026, 10, 22, 12, 0))


# Every way each roster label could plausibly be meant. The schedule must
# land inside 9 AM - 9 PM under ALL of them - that's what the 10-8 buffer
# is for (see the module docstring).
_READINGS = {
    "EST": [ZoneInfo("America/New_York"), timezone(timedelta(hours=-5))],
    "CST": [CHICAGO, timezone(timedelta(hours=-6))],
    "MST": [ZoneInfo("America/Denver"), ZoneInfo("America/Phoenix")],
    "PST": [ZoneInfo("America/Los_Angeles"), timezone(timedelta(hours=-8))],
    "HST": [ZoneInfo("Pacific/Honolulu")],
}

# Ordinary days plus both 2026 US daylight-saving switch days.
_DAYS = [(2026, 1, 15), (2026, 3, 8), (2026, 7, 1), (2026, 11, 1), (2026, 12, 31)]


@pytest.mark.parametrize("label", sorted(_READINGS))
def test_every_schedule_lands_between_9am_and_9pm_under_every_reading(label):
    checked = 0
    for day in _DAYS:
        start = datetime(*day, tzinfo=timezone.utc)
        for step in range(0, 24 * 60, 15):
            now = start + timedelta(minutes=step)
            result = next_send_time(label, now)
            assert result > now
            for reading in _READINGS[label]:
                local_hour = result.astimezone(reading).hour
                assert 9 <= local_hour < 21, f"{label} read as {reading}: {result.astimezone(reading)} (now={now})"
            checked += 1
    assert checked == len(_DAYS) * 96
