"""Tests for the uniform error format."""
from app.errors import Conflict


def test_app_error_is_rendered_as_uniform_json(client):
    @client.app.get("/_boom")
    def boom():
        raise Conflict("overlap", "This room is already booked for that time.")

    response = client.get("/_boom")
    assert response.status_code == 409
    assert response.json() == {
        "error": "overlap",
        "message": "This room is already booked for that time.",
    }