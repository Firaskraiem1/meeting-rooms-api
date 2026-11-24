# Meeting rooms API (Nordia)

A small REST API to list meeting rooms and book them, replacing an Excel sheet.
Built with Python, FastAPI and SQLite.

## Run it

Requires Python 3.10+.

```bash
python -m venv venv
venv\Scripts\activate          # Windows (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Interactive documentation (OpenAPI/Swagger): http://127.0.0.1:8000/docs

The database file `meeting_rooms.db` is created on first start and the six
rooms of `app/data/rooms.json` are loaded automatically.

Optional environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `OFFICE_TZ` | `Africa/Tunis` | Office time zone, used for business hours and "same day" |
| `DB_PATH` | `meeting_rooms.db` | SQLite file |

## Run with Docker

```bash
docker build -t meeting-rooms .
docker run --rm -p 8000:8000 meeting-rooms
```

Then open http://127.0.0.1:8000/docs.

The SQLite file lives inside the container, so data is lost when the container
is removed. To keep it, mount a volume:

```bash
docker run --rm -p 8000:8000 -e DB_PATH=/data/meeting_rooms.db -v meetingdata:/data meeting-rooms
```

## Run the tests

```bash
pytest
```

Each test uses its own temporary database and a fake clock, so results do not
depend on the real date or on previous runs.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/rooms?min_capacity=N` | List rooms, optionally with capacity >= N |
| POST | `/bookings` | Create a booking |
| DELETE | `/bookings/{id}?organiser=EMAIL` | Cancel a booking (soft delete) |
| GET | `/rooms/{id}/bookings?date=YYYY-MM-DD&limit=20&offset=0` | Bookings of a room for a local day (paginated) |

Example (the easiest way to try it is Swagger at `/docs`):

```bash
curl -X POST http://127.0.0.1:8000/bookings -H "Content-Type: application/json" -d '{
  "room_id": 1,
  "start": "2026-12-01T09:00:00+01:00",
  "end": "2026-12-01T10:00:00+01:00",
  "organiser": "firas@example.com",
  "subject": "Sprint planning"
}'
```

Use a date in the future: bookings that have already started are refused.
Times must be ISO 8601 **with an explicit UTC offset**. Responses give times
in the office time zone.

## Errors

Errors from the business rules have the form
`{"error": "<code>", "message": "<text>"}`. Clients and tests rely on the
stable `error` code, not on the wording.

| Code | HTTP | Meaning |
|---|---|---|
| `invalid_organiser` | 422 | Organiser is not an e-mail address |
| `missing_offset` | 422 | Time without UTC offset |
| `invalid_range` | 422 | End is not after start |
| `outside_hours` | 422 | Not Monday-Friday 08:00-19:00, or spans two days |
| `invalid_duration` | 422 | Shorter than 15 minutes or longer than 4 hours |
| `in_the_past` | 422 | Booking already started |
| `daily_limit` | 422 | Organiser already has 3 bookings that day |
| `room_not_found` | 404 | Unknown room |
| `booking_not_found` | 404 | Unknown booking |
| `overlap` | 409 | Room already booked for that time |
| `organiser_busy` | 409 | The organiser already has a booking at that time (any room) |
| `already_cancelled` | 409 | Booking already cancelled |
| `already_started` | 409 | Booking already started, cannot be cancelled |
| `not_organiser` | 403 | Only the organiser can cancel |

Request-validation errors raised by FastAPI itself (missing field, wrong type,
`min_capacity=0`) keep FastAPI's standard `{"detail": [...]}` format.

## Design

```
routes.py      HTTP only
service.py     business rules (no SQL, no HTTP)
repository.py  SQL only
```

Main choices (details in NOTE.md):

- **SQLite with plain `sqlite3`**: two tables, no ORM needed.
- **Times stored in UTC** in a fixed text format; business rules use office local time.
- **Only `booked` / `cancelled` are stored.** Past, ongoing and upcoming are derived from the clock, so nothing can become stale.
- **Cancelling is a soft delete**: the row stays, but the overlap check, the daily count and the day list ignore it.
- **Overlap check and insert run in one `BEGIN IMMEDIATE` transaction.**
- **Injectable clock** in the service, so time-dependent rules are testable.

## Assumptions

- Two bookings that touch (one ends at 10:00, the next starts at 10:00) do not overlap.
- "Active" booking = status `booked` (not cancelled), whether finished or still to come. The limit of 3 is per organiser and per local calendar day, counted on the day the booking starts. Cancelling frees both the slot and one of the 3.
- Back-to-back bookings by the same person are allowed, so one person can still keep a room for most of the day within the rules. However, an organiser cannot hold two overlapping bookings, even in different rooms (`organiser_busy`). Cancelling frees the organiser.
- Only the organiser (e-mail, case-insensitive) can cancel a booking. See "Security limits".
- A booking must start and end on the same local day and cannot start in the past. There is no maximum horizon in the future.
- Only Saturday and Sunday are excluded; public holidays are not handled.
- An e-mail is only checked for containing "@" and is stored in lower case.
- A booking cannot be modified: cancel it and create a new one.
- Time zone: one office time zone, `Africa/Tunis` by default (UTC+1, no daylight saving). Other zones are supported through `OFFICE_TZ` but only Tunis is tested.

## Security limits

- **There is no authentication.** The organiser is a declared e-mail address,
  not a verified identity. The "only the organiser can cancel" rule is a
  consistency check, **not a security control**: anyone who knows an e-mail
  can cancel that person's bookings, or book in their name.
- Next step: API keys or JWT, with the organiser taken from the credential.

## Not done

- No frontend (the brief asks for an API).
- No authentication (see "Security limits").
- Time zone conversion is only tested with `Africa/Tunis`; other zones and daylight-saving changes are untested.
- Filtering the room bookings list by past / ongoing / upcoming.
- FastAPI's own validation errors keep the `{"detail": [...]}` format.