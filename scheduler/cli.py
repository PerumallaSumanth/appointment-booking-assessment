"""Interactive command-line front end for the in-memory booking service.

Commands (one per line):
  book <provider_id> <start_utc> <end_utc>
  cancel <appointment_id>
  list <provider_id> [--all]
  help
  quit

Timestamps are ISO-8601 in UTC, e.g. 2026-12-01T09:00:00Z.
State lives in memory for the lifetime of the session.
"""
from __future__ import annotations

import shlex
import sys
from typing import List, TextIO

from .service import AppointmentService, BookingError, CancelOutcome


def _fmt(a) -> str:
    return (f"{a.id}  provider={a.provider_id}  "
            f"{a.start.isoformat().replace('+00:00', 'Z')} -> "
            f"{a.end.isoformat().replace('+00:00', 'Z')}  {a.status.value}")


def handle(service: AppointmentService, line: str) -> str:
    try:
        parts: List[str] = shlex.split(line)
    except ValueError as exc:
        return f"ERROR INVALID_INPUT: {exc}"
    if not parts:
        return ""
    cmd, args = parts[0].lower(), parts[1:]
    try:
        if cmd == "book":
            if len(args) != 3:
                return "ERROR INVALID_INPUT: usage: book <provider_id> <start_utc> <end_utc>"
            appt = service.book(*args)
            return f"BOOKED {_fmt(appt)}"
        if cmd == "cancel":
            if len(args) != 1:
                return "ERROR INVALID_INPUT: usage: cancel <appointment_id>"
            result = service.cancel(args[0])
            if result.outcome is CancelOutcome.CANCELLED:
                return f"CANCELLED {result.appointment.id}"
            return f"ERROR {result.outcome.value}: {args[0]}"
        if cmd == "list":
            if not args:
                return "ERROR INVALID_INPUT: usage: list <provider_id> [--all]"
            appts = service.list_for_provider(args[0], include_cancelled="--all" in args[1:])
            return "\n".join(_fmt(a) for a in appts) or "(no appointments)"
        if cmd == "help":
            return __doc__.strip()
        return f"ERROR INVALID_INPUT: unknown command {cmd!r} (try 'help')"
    except BookingError as exc:
        return f"ERROR {exc.code}: {exc}"


def main(stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> int:
    service = AppointmentService()
    interactive = stdin.isatty()
    if interactive:
        print("Appointment booking (UTC). Type 'help' for commands.", file=stdout)
    while True:
        if interactive:
            print("> ", end="", file=stdout, flush=True)
        line = stdin.readline()
        if not line:
            break
        if line.strip().lower() in {"quit", "exit"}:
            break
        out = handle(service, line)
        if out:
            print(out, file=stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
