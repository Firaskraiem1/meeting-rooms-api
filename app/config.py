"""Application settings and shared constants.

Values can be overridden with environment variables so the same code
runs locally, in tests and in Docker.
"""
import os

# Time zone of the (single) Nordia office. Business hours use this zone.
TIMEZONE = os.getenv("OFFICE_TZ", "Africa/Tunis")
DB_PATH = os.getenv("DB_PATH", "meeting_rooms.db")

# Stored booking statuses. Past / ongoing / upcoming are derived from the
# clock, never stored.
BOOKED = "booked"
CANCELLED = "cancelled"