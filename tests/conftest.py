"""Shared test fixtures: a temporary database for every test."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A test client whose database is a fresh file, deleted after the test."""
    monkeypatch.setattr("app.db.DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as test_client:
        yield test_client