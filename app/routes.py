"""HTTP routes. They only translate HTTP to service/repository calls."""
from fastapi import APIRouter, Depends, Query, Request

from .repository import Repository
from .schemas import RoomOut

router = APIRouter()


def get_repo(request: Request) -> Repository:
    """Provide a repository bound to the application's database."""
    return Repository(request.app.state.conn)


@router.get("/rooms", response_model=list[RoomOut])
def list_rooms(
    min_capacity: int | None = Query(None, ge=1, description="Minimum number of seats"),
    repo: Repository = Depends(get_repo),
):
    """List the rooms, optionally keeping only those with enough seats."""
    return repo.list_rooms(min_capacity)