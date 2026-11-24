"""Tests for the rooms endpoint."""


def test_list_rooms_returns_all_six(client):
    response = client.get("/rooms")
    assert response.status_code == 200
    assert len(response.json()) == 6


def test_min_capacity_filters_rooms(client):
    response = client.get("/rooms", params={"min_capacity": 10})
    names = [r["name"] for r in response.json()]
    assert names == ["Delta", "Equinox", "Fjord"]


def test_min_capacity_boundary_excludes_smaller_room(client):
    response = client.get("/rooms", params={"min_capacity": 11})
    names = [r["name"] for r in response.json()]
    assert names == ["Equinox", "Fjord"]


def test_invalid_min_capacity_is_rejected(client):
    response = client.get("/rooms", params={"min_capacity": 0})
    assert response.status_code == 422