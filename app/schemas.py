"""Pydantic models describing what the API returns."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel,EmailStr, Field


class RoomOut(BaseModel):
    """A meeting room."""
    id: int
    name: str
    capacity: int
    floor: int
    equipment: list[str]

class BookingIn(BaseModel):
    """What a client sends to create a booking."""
    room_id: int
    start: datetime = Field(description="ISO 8601 with UTC offset, e.g. 2026-12-01T09:00:00+01:00")
    end: datetime = Field(description="ISO 8601 with UTC offset")
    organiser: str = Field(min_length=3, max_length=254, description="Organiser e-mail")
    subject: str = Field(min_length=1, max_length=200)


class BookingOut(BaseModel):
    """A booking as returned by the API (times in the office time zone)."""
    id: int
    room_id: int
    organiser: str
    subject: str
    start: datetime
    end: datetime
    status: Literal["booked", "cancelled"]