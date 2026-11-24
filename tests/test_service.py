"""Tests for the booking rules (no HTTP, no database for the early rules)."""
from datetime import datetime, timedelta, timezone

import pytest

from app.errors import RuleViolation
from app.service import BookingService

TUNIS = timezone(timedelta(hours=1))
NOW = datetime(2026, 11, 30, 12, 0, tzinfo=TUNIS)  # Monday, before the slots


def at(day, h, m=0):
    """Datetime in office time. 1 Dec 2026 is a Tuesday, 5 Dec a Saturday."""
    return datetime(2026, 12, day, h, m, tzinfo=TUNIS)


def make_service(now=NOW):
    # repo=None is enough: these rules fail before any database access.
    return BookingService(repo=None, tz="Africa/Tunis", clock=lambda: now)


def code_of(service, start, end):
    """Run create() and return the code of the RuleViolation it raises."""
    with pytest.raises(RuleViolation) as exc:
        service.create(1, start, end, "a@x.com", "Sprint")
    return exc.value.code


def test_naive_datetime_is_rejected():
    start, end = datetime(2026, 12, 1, 9), datetime(2026, 12, 1, 10)
    assert code_of(make_service(), start, end) == "missing_offset"


def test_end_before_start_is_rejected():
    assert code_of(make_service(), at(1, 10), at(1, 9)) == "invalid_range"


def test_before_opening_is_rejected():
    assert code_of(make_service(), at(1, 7, 30), at(1, 8, 30)) == "outside_hours"


def test_ending_after_closing_is_rejected():
    assert code_of(make_service(), at(1, 18, 30), at(1, 19, 15)) == "outside_hours"


def test_weekend_is_rejected():
    assert code_of(make_service(), at(5, 9), at(5, 10)) == "outside_hours"


def test_too_short_is_rejected():
    assert code_of(make_service(), at(1, 9), at(1, 9, 14)) == "invalid_duration"


def test_too_long_is_rejected():
    assert code_of(make_service(), at(1, 9), at(1, 13, 1)) == "invalid_duration"


def test_past_slot_is_rejected():
    service = make_service(now=at(1, 10))
    assert code_of(service, at(1, 9), at(1, 9, 30)) == "in_the_past"