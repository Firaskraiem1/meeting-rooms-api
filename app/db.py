"""SQLite connection, schema creation and loading of the provided rooms."""
import json
import sqlite3
from pathlib import Path

from .config import BOOKED, CANCELLED, DB_PATH

ROOMS_FILE = Path(__file__).parent / "data" / "rooms.json"

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS rooms (
    id        INTEGER PRIMARY KEY,
    name      TEXT NOT NULL,
    capacity  INTEGER NOT NULL,
    floor     INTEGER NOT NULL,
    equipment TEXT NOT NULL            -- JSON list
);

CREATE TABLE IF NOT EXISTS bookings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id      INTEGER NOT NULL REFERENCES rooms(id),
    organiser    TEXT    NOT NULL,     -- e-mail, lower case
    subject      TEXT    NOT NULL,
    start_utc    TEXT    NOT NULL,     -- 'YYYY-MM-DDTHH:MM:SSZ'
    end_utc      TEXT    NOT NULL,
    status       TEXT    NOT NULL DEFAULT '{BOOKED}'
                 CHECK (status IN ('{BOOKED}', '{CANCELLED}')),
    created_at   TEXT    NOT NULL,
    cancelled_at TEXT,
    CHECK (end_utc > start_utc)
);

CREATE INDEX IF NOT EXISTS idx_bookings_room_start
    ON bookings(room_id, start_utc);
CREATE INDEX IF NOT EXISTS idx_bookings_organiser_start
    ON bookings(organiser, start_utc);
"""


def connect(path: str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection configured for this application.

    Transactions are managed manually (isolation_level=None) so the
    repository can use BEGIN IMMEDIATE. Foreign keys are enabled because
    SQLite ignores them by default.
    """
    conn = sqlite3.connect(path or DB_PATH, isolation_level=None,
                           check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create the tables if needed and load the rooms. Safe to call twice."""
    conn.executescript(SCHEMA)
    load_rooms(conn)


def load_rooms(conn: sqlite3.Connection, path: Path = ROOMS_FILE) -> None:
    """Insert the rooms from rooms.json, only if the table is still empty."""
    if conn.execute("SELECT COUNT(*) FROM rooms").fetchone()[0] > 0:
        return
    rooms = json.loads(path.read_text(encoding="utf-8"))
    for r in rooms:
        conn.execute(
            "INSERT INTO rooms (id, name, capacity, floor, equipment) "
            "VALUES (?, ?, ?, ?, ?)",
            (r["id"], r["name"], r["capacity"], r["floor"],
             json.dumps(r["equipment"])),
        )