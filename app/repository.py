"""Database access. Contains SQL only, no business rules."""
import json
import sqlite3


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