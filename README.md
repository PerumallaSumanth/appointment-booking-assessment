# Appointment B: Conflict-Safe Booking and Cancellation

A small in-memory Python service, with a command-line front end, that books and cancels provider appointments. A provider can never have two **active** appointments that overlap. No starter project was supplied, so this is the minimal service and CLI described in the assessment. There is no frontend, no database and no authentication.

## Layout

```
scheduler/
  service.py      # AppointmentService: book, cancel, get, list_for_provider
  cli.py          # line-based CLI over the service
tests/
  test_service.py # acceptance-criteria tests, including concurrency
  test_cli.py     # CLI smoke tests
FINDINGS.md       # one-page summary of results, test and mutation evidence, risks
DESIGN.md         # design specification
NOTES.md          # assumptions, booking invariant, limitations and follow-up risks
AI_USE_RECORD.md  # prompts, AI output summary, accept/edit/reject decisions, verification
```

## Setup

Requires Python 3.9 or later. The service uses only the standard library; the tests need pytest.

```bash
cd appointment-booking
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

## Run the tests

```bash
python -m pytest -v
```

Expected result: `34 passed`.

## Run the CLI

Interactive:

```bash
python -m scheduler.cli
> book dr-1 2026-12-01T09:00:00Z 2026-12-01T09:30:00Z
> book dr-1 2026-12-01T09:15:00Z 2026-12-01T09:45:00Z     # ERROR CONFLICT
> book dr-1 2026-12-01T09:30:00Z 2026-12-01T10:00:00Z     # adjacent: BOOKED
> cancel <id-from-first-booking>
> list dr-1 --all
> quit
```

Scripted:

```bash
printf 'book dr-1 2026-12-01T09:00:00Z 2026-12-01T09:30:00Z\nlist dr-1\n' | python -m scheduler.cli
```

Every response starts with one of these:

- `BOOKED`
- `CANCELLED`
- `ERROR CONFLICT`
- `ERROR INVALID_INPUT`
- `ERROR NOT_FOUND`
- `ERROR ALREADY_CANCELLED`

## Use as a library

```python
from scheduler import AppointmentService, ConflictError, ValidationError

svc = AppointmentService()
appt = svc.book("dr-1", "2026-12-01T09:00:00Z", "2026-12-01T09:30:00Z")
result = svc.cancel(appt.id)       # result.outcome: CANCELLED | NOT_FOUND | ALREADY_CANCELLED
```
