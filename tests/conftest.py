"""Shared test fixtures: temporary database and controllable clock."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repository import Repository
from app.routes import get_service
from app.service import BookingService

TUNIS = timezone(timedelta(hours=1))


class FakeClock:
    """A clock tests can move: call it to get 'now', set .now to change it."""

    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    """Monday 30 Nov 2026, 12:00 (office time): before the test slots."""
    return FakeClock(datetime(2026, 11, 30, 12, 0, tzinfo=TUNIS))


@pytest.fixture
def client(tmp_path, monkeypatch, clock):
    """A test client with a fresh database and the fake clock."""
    monkeypatch.setattr("app.db.DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as test_client:
        app.dependency_overrides[get_service] = lambda: BookingService(
            Repository(app.state.conn), clock=clock)
        yield test_client
        app.dependency_overrides.clear()