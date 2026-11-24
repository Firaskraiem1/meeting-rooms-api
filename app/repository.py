"""Database access. Contains SQL only, no business rules."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from .config import BOOKED, CANCELLED

class Repository:
    """Thin wrapper around a SQLite connection."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def list_rooms(self, min_capacity: int | None = None) -> list[dict]:
        """Return rooms ordered by id, optionally with capacity >= min_capacity."""
        sql = "SELECT id, name, capacity, floor, equipment FROM rooms"
        params: list = []
        if min_capacity is not None:
            sql += " WHERE capacity >= ?"
            params.append(min_capacity)
        sql += " ORDER BY id"
        rows = self.conn.execute(sql, params).fetchall()
        return [
            {**dict(r), "equipment": json.loads(r["equipment"])}
            for r in rows
        ]
    # ---------- helpers ----------

    @staticmethod
    def to_db(dt: datetime) -> str:
        """Format a datetime as UTC text 'YYYY-MM-DDTHH:MM:SSZ'.

        The format is always identical, so SQLite can compare the
        strings with < and > and get chronological order.
        """
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def from_db(text: str) -> datetime:
        """Parse the stored UTC text back into an aware datetime."""
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

    @contextmanager
    def transaction(self):
        """Run a block atomically. BEGIN IMMEDIATE locks writers right away,
        so the overlap check and the insert cannot be interleaved by
        another request."""
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    # ---------- rooms ----------

    def room_exists(self, room_id: int) -> bool:
        """Tell whether a room with this id exists."""
        row = self.conn.execute("SELECT 1 FROM rooms WHERE id = ?", (room_id,)).fetchone()
        return row is not None

    # ---------- bookings ----------

    def has_overlap(self, room_id: int, start: datetime, end: datetime) -> bool:
        """True if a booked slot of this room overlaps [start, end).

        Strict inequalities: a booking ending at 10:00 does not overlap
        one starting at 10:00. Cancelled bookings are ignored.
        """
        row = self.conn.execute(
            "SELECT 1 FROM bookings "
            "WHERE room_id = ? AND status = ? AND start_utc < ? AND end_utc > ? "
            "LIMIT 1",
            (room_id, BOOKED, self.to_db(end), self.to_db(start)),
        ).fetchone()
        return row is not None

    def count_booked(self, organiser: str, day_start: datetime, day_end: datetime) -> int:
        """Count the organiser's non-cancelled bookings starting in [day_start, day_end).

        Finished bookings count too (our reading of "active").
        """
        row = self.conn.execute(
            "SELECT COUNT(*) FROM bookings "
            "WHERE organiser = ? AND status = ? AND start_utc >= ? AND start_utc < ?",
            (organiser, BOOKED, self.to_db(day_start), self.to_db(day_end)),
        ).fetchone()
        return row[0]

    def insert(self, room_id, start, end, organiser, subject, now: datetime) -> dict:
        """Insert a booked booking and return it."""
        cur = self.conn.execute(
            "INSERT INTO bookings "
            "(room_id, organiser, subject, start_utc, end_utc, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (room_id, organiser, subject, self.to_db(start), self.to_db(end),
             BOOKED, self.to_db(now)),
        )
        return self.get(cur.lastrowid)

    def get(self, booking_id: int) -> dict | None:
        """Return one booking as a dict with aware datetimes, or None."""
        row = self.conn.execute(
            "SELECT id, room_id, organiser, subject, start_utc, end_utc, status "
            "FROM bookings WHERE id = ?",
            (booking_id,),
        ).fetchone()
        return self._booking(row) if row else None

    def mark_cancelled(self, booking_id: int, now: datetime) -> None:
        """Soft delete: keep the row, set status to cancelled."""
        self.conn.execute(
            "UPDATE bookings SET status = ?, cancelled_at = ? WHERE id = ?",
            (CANCELLED, self.to_db(now), booking_id),
        )

    def list_for_day(self, room_id: int, day_start: datetime, day_end: datetime,
                     limit: int | None = None, offset: int = 0) -> tuple[list[dict], int]:
        """Return (bookings, total) of a room for a day, ordered by start.

        Only booked (non-cancelled) bookings, including finished ones.
        limit/offset are optional so pagination can be added later.
        """
        where = "room_id = ? AND status = ? AND start_utc >= ? AND start_utc < ?"
        params = (room_id, BOOKED, self.to_db(day_start), self.to_db(day_end))
        total = self.conn.execute(f"SELECT COUNT(*) FROM bookings WHERE {where}", params).fetchone()[0]
        sql = (f"SELECT id, room_id, organiser, subject, start_utc, end_utc, status "
               f"FROM bookings WHERE {where} ORDER BY start_utc")
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params = params + (limit, offset)
        rows = self.conn.execute(sql, params).fetchall()
        return [self._booking(r) for r in rows], total

    def _booking(self, row) -> dict:
        """Convert a database row into a dict with aware datetimes."""
        data = dict(row)
        data["start"] = self.from_db(data.pop("start_utc"))
        data["end"] = self.from_db(data.pop("end_utc"))
        return data