"""End-to-end tests of the booking endpoints (HTTP, service, SQLite)."""
from datetime import datetime, timedelta

from datetime import datetime, timedelta, timezone

TUNIS = timezone(timedelta(hours=1))


def slot(h1, m1, h2, m2, day=1):
    """Start/end strings in office time. 1 Dec 2026 is a Tuesday."""
    return (f"2026-12-{day:02d}T{h1:02d}:{m1:02d}:00+01:00",
            f"2026-12-{day:02d}T{h2:02d}:{m2:02d}:00+01:00")


def book(client, h1, m1, h2, m2, room=1, organiser="a@x.com", day=1):
    start, end = slot(h1, m1, h2, m2, day)
    return client.post("/bookings", json={
        "room_id": room, "start": start, "end": end,
        "organiser": organiser, "subject": "Sprint"})


def test_valid_booking_is_created(client):
    response = book(client, 9, 0, 10, 0)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "booked"
    assert body["start"].endswith("+01:00")


def test_overlap_is_refused(client):
    book(client, 9, 0, 10, 0)
    response = book(client, 9, 30, 10, 30, organiser="b@x.com")
    assert response.status_code == 409
    assert response.json()["error"] == "overlap"


def test_touching_bookings_are_accepted(client):
    book(client, 9, 0, 10, 0)
    assert book(client, 10, 0, 11, 0, organiser="b@x.com").status_code == 201


def test_boundary_durations_and_closing_time_are_accepted(client):
    assert book(client, 9, 0, 9, 15).status_code == 201     # 15 min
    assert book(client, 10, 0, 14, 0).status_code == 201    # 4 h
    assert book(client, 18, 0, 19, 0).status_code == 201    # ends at 19:00


def test_fourth_booking_of_the_day_is_refused_until_one_is_cancelled(client):
    for hour in (8, 9, 10):
        assert book(client, hour, 0, hour, 30).status_code == 201
    refused = book(client, 11, 0, 11, 30)
    assert refused.status_code == 422
    assert refused.json()["error"] == "daily_limit"

    client.delete("/bookings/1", params={"organiser": "a@x.com"})
    assert book(client, 11, 0, 11, 30).status_code == 201


def test_limit_is_per_organiser_and_per_day(client):
    for hour in (8, 9, 10):
        book(client, hour, 0, hour, 30)
    assert book(client, 11, 0, 11, 30, organiser="b@x.com").status_code == 201
    assert book(client, 8, 0, 8, 30, day=2).status_code == 201


def test_other_organiser_cannot_cancel(client):
    booking_id = book(client, 9, 0, 10, 0).json()["id"]
    response = client.delete(f"/bookings/{booking_id}",
                             params={"organiser": "b@x.com"})
    assert response.status_code == 403
    assert response.json()["error"] == "not_organiser"


def test_started_booking_cannot_be_cancelled(client, clock):
    booking_id = book(client, 9, 0, 10, 0).json()["id"]
    clock.now = datetime(2026, 12, 1, 9, 30, tzinfo=TUNIS)   # meeting in progress
    response = client.delete(f"/bookings/{booking_id}",
                             params={"organiser": "a@x.com"})
    assert response.status_code == 409
    assert response.json()["error"] == "already_started"


def test_cancelled_slot_can_be_booked_again(client):
    booking_id = book(client, 9, 0, 10, 0).json()["id"]
    cancelled = client.delete(f"/bookings/{booking_id}",
                              params={"organiser": "a@x.com"})
    assert cancelled.json()["status"] == "cancelled"
    assert book(client, 9, 0, 10, 0, organiser="b@x.com").status_code == 201


def test_unknown_room_returns_404(client):
    response = book(client, 9, 0, 10, 0, room=99)
    assert response.status_code == 404
    assert response.json()["error"] == "room_not_found"


def test_day_list_is_ordered_paginated_and_hides_cancelled(client):
    book(client, 14, 0, 15, 0)
    book(client, 9, 0, 10, 0)
    cancelled_id = book(client, 11, 0, 12, 0).json()["id"]
    client.delete(f"/bookings/{cancelled_id}", params={"organiser": "a@x.com"})

    response = client.get("/rooms/1/bookings", params={"date": "2026-12-01"})
    body = response.json()
    starts = [b["start"][11:16] for b in body["items"]]
    assert starts == ["09:00", "14:00"]
    assert body["total"] == 2

    page = client.get("/rooms/1/bookings",
                      params={"date": "2026-12-01", "limit": 1, "offset": 1}).json()
    assert [b["start"][11:16] for b in page["items"]] == ["14:00"]
    assert page["total"] == 2

def test_organiser_cannot_book_two_rooms_at_the_same_time(client):
    assert book(client, 9, 0, 10, 0, room=1).status_code == 201
    response = book(client, 9, 30, 10, 30, room=2)   # same organiser, other room
    assert response.status_code == 409
    assert response.json()["error"] == "organiser_busy"


def test_organiser_can_book_two_rooms_back_to_back(client):
    assert book(client, 9, 0, 10, 0, room=1).status_code == 201
    assert book(client, 10, 0, 11, 0, room=2).status_code == 201


def test_different_organisers_can_book_different_rooms_at_the_same_time(client):
    assert book(client, 9, 0, 10, 0, room=1).status_code == 201
    assert book(client, 9, 0, 10, 0, room=2, organiser="b@x.com").status_code == 201


def test_cancelling_frees_the_organiser(client):
    first = book(client, 9, 0, 10, 0, room=1).json()["id"]
    client.delete(f"/bookings/{first}", params={"organiser": "a@x.com"})
    assert book(client, 9, 0, 10, 0, room=2).status_code == 201

def test_cancelling_twice_returns_409(client):
    booking_id = book(client, 9, 0, 10, 0).json()["id"]
    client.delete(f"/bookings/{booking_id}", params={"organiser": "a@x.com"})
    response = client.delete(f"/bookings/{booking_id}", params={"organiser": "a@x.com"})
    assert response.status_code == 409
    assert response.json()["error"] == "already_cancelled"


def test_cancelling_unknown_booking_returns_404(client):
    response = client.delete("/bookings/999", params={"organiser": "a@x.com"})
    assert response.status_code == 404
    assert response.json()["error"] == "booking_not_found"