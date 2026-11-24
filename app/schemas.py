"""Pydantic models describing what the API returns."""
from pydantic import BaseModel


class RoomOut(BaseModel):
    """A meeting room."""
    id: int
    name: str
    capacity: int
    floor: int
    equipment: list[str]