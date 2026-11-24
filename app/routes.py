"""HTTP routes. They only translate HTTP to service/repository calls."""
from datetime import date

from fastapi import APIRouter, Depends, Query, Request

from .repository import Repository
from .schemas import BookingIn, BookingOut, BookingPage, RoomOut
from .service import BookingService

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

def get_service(repo: Repository = Depends(get_repo)) -> BookingService:
    """Provide the booking service bound to a repository."""
    return BookingService(repo)


@router.post("/bookings", response_model=BookingOut, status_code=201)
def create_booking(body: BookingIn, service: BookingService = Depends(get_service)):
    """Create a booking. All business rules are applied by the service."""
    return service.create(body.room_id, body.start, body.end,
                          body.organiser, body.subject)


@router.delete("/bookings/{booking_id}", response_model=BookingOut)
def cancel_booking(
    booking_id: int,
    organiser: str = Query(..., description="E-mail of the organiser"),
    service: BookingService = Depends(get_service),
):
    """Cancel a booking. Only its organiser can, and only before it starts."""
    return service.cancel(booking_id, organiser)


@router.get("/rooms/{room_id}/bookings", response_model=BookingPage)
def list_room_bookings(
    room_id: int,
    day: date = Query(..., alias="date", description="Local day, YYYY-MM-DD"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: BookingService = Depends(get_service),
):
    """List the non-cancelled bookings of a room for a day (finished ones included)."""
    items, total = service.list_room_bookings(room_id, day, limit, offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}