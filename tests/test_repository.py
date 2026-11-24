"""Tests for the SQL layer."""
from datetime import datetime, timezone

from app.db import connect, init_db
from app.repository import Repository


def make_repo(tmp_path):
    conn = connect(str(tmp_path / "repo.db"))
    init_db(conn)
    return Repository(conn)


def utc(h, m=0):
    return datetime(2026, 12, 1, h, m, tzinfo=timezone.utc)


def test_touching_bookings_do_not_overlap(tmp_path):
    repo = make_repo(tmp_path)
    now = utc(0)
    repo.insert(1, utc(9), utc(10), "a@x.com", "first", now)
    assert repo.has_overlap(1, utc(10), utc(11)) is False   # touches at 10:00
    assert repo.has_overlap(1, utc(9, 30), utc(10, 30)) is True


def test_cancelled_booking_does_not_block_the_room(tmp_path):
    repo = make_repo(tmp_path)
    now = utc(0)
    booking = repo.insert(1, utc(9), utc(10), "a@x.com", "first", now)
    repo.mark_cancelled(booking["id"], now)
    assert repo.has_overlap(1, utc(9), utc(10)) is False

def test_count_booked_counts_only_this_organiser_and_day(tmp_path):
    repo = make_repo(tmp_path)
    now = utc(0)
    day_start = datetime(2026, 12, 1, 0, 0, tzinfo=timezone.utc)
    day_end = datetime(2026, 12, 2, 0, 0, tzinfo=timezone.utc)

    first = repo.insert(1, utc(8), utc(9), "a@x.com", "one", now)
    repo.insert(2, utc(10), utc(11), "a@x.com", "two", now)
    repo.insert(3, utc(12), utc(13), "a@x.com", "three", now)
    repo.insert(1, utc(14), utc(15), "b@x.com", "other person", now)
    repo.insert(1, datetime(2026, 12, 2, 9, tzinfo=timezone.utc),
                datetime(2026, 12, 2, 10, tzinfo=timezone.utc),
                "a@x.com", "other day", now)

    assert repo.count_booked("a@x.com", day_start, day_end) == 3

    repo.mark_cancelled(first["id"], now)
    assert repo.count_booked("a@x.com", day_start, day_end) == 2

def test_organiser_overlap_spans_all_rooms(tmp_path):
    repo = make_repo(tmp_path)
    now = utc(0)
    repo.insert(1, utc(9), utc(10), "a@x.com", "first", now)
    assert repo.organiser_has_overlap("a@x.com", utc(9, 30), utc(10, 30)) is True
    assert repo.organiser_has_overlap("a@x.com", utc(10), utc(11)) is False   # touching
    assert repo.organiser_has_overlap("b@x.com", utc(9, 30), utc(10, 30)) is False

