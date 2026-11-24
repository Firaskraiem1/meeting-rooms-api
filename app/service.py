"""Business rules for bookings. No SQL and no HTTP here."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .config import CANCELLED, TIMEZONE
from .errors import Conflict, Forbidden, NotFound, RuleViolation

OPEN, CLOSE = time(8, 0), time(19, 0)
MIN_DURATION, MAX_DURATION = timedelta(minutes=15), timedelta(hours=4)
MAX_PER_DAY = 3


class BookingService:
    """Applies the Nordia booking rules on top of the repository.

    Assumptions (also written in NOTE.md):
    - "Active" booking = status `booked` (not cancelled), finished or not.
    - Only the organiser (e-mail, case-insensitive) can cancel a booking.
    - A booking cannot start in the past and must fit within one local day.
    """

    def __init__(self, repo, tz: str = TIMEZONE, clock=None):
        self.repo = repo
        self.tz = ZoneInfo(tz)
        # Injectable clock: tests can freeze "now".
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    # ---------- helpers ----------

    def _present(self, booking: dict) -> dict:
        """Return the booking with start/end expressed in office time."""
        return {**booking,
                "start": booking["start"].astimezone(self.tz),
                "end": booking["end"].astimezone(self.tz)}

    def _local_day_bounds(self, day: date) -> tuple[datetime, datetime]:
        """Return [00:00, next 00:00) of a local day as aware datetimes."""
        start = datetime.combine(day, time(0, 0), tzinfo=self.tz)
        end = datetime.combine(day + timedelta(days=1), time(0, 0), tzinfo=self.tz)
        return start, end

    # ---------- use cases ----------

    def create(self, room_id, start, end, organiser, subject):
        """Create a booking after checking every rule."""
        organiser = organiser.strip().lower()
        if "@" not in organiser:
            raise RuleViolation("invalid_organiser",
                                "Organiser must be an e-mail address.")

        # Rule 0: explicit offset, coherent range.
        if start.tzinfo is None or end.tzinfo is None:
            raise RuleViolation("missing_offset",
                                "Times must include a UTC offset (ISO 8601).")
        if end <= start:
            raise RuleViolation("invalid_range", "End must be after start.")

        # Rule 1: Monday-Friday, 08:00-19:00 office time, within one day.
        local_start = start.astimezone(self.tz)
        local_end = end.astimezone(self.tz)
        if (local_start.date() != local_end.date()
                or local_start.weekday() >= 5
                or local_start.time() < OPEN
                or local_end.time() > CLOSE):
            raise RuleViolation(
                "outside_hours",
                "Bookings are possible Monday to Friday, 08:00-19:00, within one day.")

        # Rule 2: duration between 15 minutes and 4 hours.
        if not (MIN_DURATION <= end - start <= MAX_DURATION):
            raise RuleViolation(
                "invalid_duration",
                "A booking lasts at least 15 minutes and at most 4 hours.")

        # Rule 3: not in the past (our assumption).
        now = self.clock()
        if start <= now:
            raise RuleViolation("in_the_past",
                                "Cannot book a slot that has already started.")

        # Rule 4: the room must exist.
        if not self.repo.room_exists(room_id):
            raise NotFound("room_not_found", f"Room {room_id} does not exist.")

        # Rules 5 and 6 need the database: check AND insert in ONE transaction
        # so two concurrent requests cannot both see the slot as free.
        with self.repo.transaction():
            if self.repo.has_overlap(room_id, start, end):
                raise Conflict("overlap",
                               "This room is already booked for that time.")

            day_start, day_end = self._local_day_bounds(local_start.date())
            if self.repo.count_booked(organiser, day_start, day_end) >= MAX_PER_DAY:
                raise RuleViolation(
                    "daily_limit",
                    "An organiser cannot have more than 3 active bookings on the same day.")

            booking = self.repo.insert(room_id, start, end, organiser, subject, now)
        return self._present(booking)

    def cancel(self, booking_id: int, organiser: str):
        """Cancel a booking: only its organiser, and only before it starts."""
        booking = self.repo.get(booking_id)
        if booking is None:
            raise NotFound("booking_not_found", "Booking not found.")
        if booking["organiser"] != organiser.strip().lower():
            raise Forbidden("not_organiser",
                            "Only the organiser can cancel this booking.")
        if booking["status"] == CANCELLED:
            raise Conflict("already_cancelled", "Booking is already cancelled.")
        now = self.clock()
        if booking["start"] <= now:
            raise Conflict("already_started",
                           "A booking that has started cannot be cancelled.")
        self.repo.mark_cancelled(booking_id, now)
        return self._present(self.repo.get(booking_id))

    def list_room_bookings(self, room_id: int, day: date,
                           limit: int | None = None, offset: int = 0):
        """Return (bookings, total) of a room for a local day, ordered by start.

        Non-cancelled bookings only, finished ones included.
        """
        if not self.repo.room_exists(room_id):
            raise NotFound("room_not_found", f"Room {room_id} does not exist.")
        day_start, day_end = self._local_day_bounds(day)
        items, total = self.repo.list_for_day(room_id, day_start, day_end, limit, offset)
        return [self._present(b) for b in items], total