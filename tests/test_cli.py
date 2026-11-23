import io

from scheduler.cli import handle, main
from scheduler import AppointmentService


def test_cli_book_conflict_cancel_rebook():
    svc = AppointmentService()
    out = handle(svc, "book dr-1 2026-12-01T09:00:00Z 2026-12-01T09:30:00Z")
    assert out.startswith("BOOKED ")
    appt_id = out.split()[1]

    assert handle(svc, "book dr-1 2026-12-01T09:15:00Z 2026-12-01T09:45:00Z").startswith("ERROR CONFLICT")
    assert handle(svc, f"cancel {appt_id}") == f"CANCELLED {appt_id}"
    assert handle(svc, f"cancel {appt_id}").startswith("ERROR ALREADY_CANCELLED")
    assert handle(svc, "cancel nope").startswith("ERROR NOT_FOUND")
    assert handle(svc, "book dr-1 2026-12-01T09:15:00Z 2026-12-01T09:45:00Z").startswith("BOOKED ")


def test_cli_invalid_input():
    svc = AppointmentService()
    assert handle(svc, "book dr-1 bad 2026-12-01T09:30:00Z").startswith("ERROR INVALID_INPUT")
    assert handle(svc, "book dr-1").startswith("ERROR INVALID_INPUT")
    assert handle(svc, "frobnicate").startswith("ERROR INVALID_INPUT")


def test_cli_main_reads_script():
    script = io.StringIO(
        "book dr-1 2026-12-01T09:00:00Z 2026-12-01T09:30:00Z\n"
        "book dr-1 2026-12-01T09:30:00Z 2026-12-01T10:00:00Z\n"
        "list dr-1\n"
        "quit\n"
    )
    out = io.StringIO()
    assert main(stdin=script, stdout=out) == 0
    lines = out.getvalue().strip().splitlines()
    assert sum(l.startswith("BOOKED") for l in lines) == 2
    assert sum("ACTIVE" in l for l in lines) == 4  # 2 BOOKED + 2 listed
