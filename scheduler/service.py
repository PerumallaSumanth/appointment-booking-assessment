"""Conflict-safe appointment booking and cancellation (in-memory).

Booking invariant: for any provider, no two ACTIVE appointments have
overlapping half-open intervals [start, end). Intervals that merely touch
(one ends exactly when the next starts) do not overlap.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Union

TimeInput = Union[str, datetime]


class Status(str, Enum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class Appointment:
    id: str
    provider_id: str
    start: datetime  # timezone-aware, UTC
    end: datetime    # timezone-aware, UTC, end > start
    status: Status = Status.ACTIVE


class BookingError(Exception):
    """Base class for all expected booking failures."""
    code = "BOOKING_ERROR"


class ValidationError(BookingError):
    code = "INVALID_INPUT"


class ConflictError(BookingError):
    code = "CONFLICT"

    def __init__(self, message: str, conflicting_id: str):
        super().__init__(message)
        self.conflicting_id = conflicting_id


class CancelOutcome(str, Enum):
    CANCELLED = "CANCELLED"
    NOT_FOUND = "NOT_FOUND"
    ALREADY_CANCELLED = "ALREADY_CANCELLED"


@dataclass(frozen=True)
class CancelResult:
    outcome: CancelOutcome
    appointment: Optional[Appointment] = None

    @property
    def ok(self) -> bool:
        return self.outcome is CancelOutcome.CANCELLED


def parse_utc(value: TimeInput, field: str) -> datetime:
    """Parse an ISO-8601 timestamp that must carry an explicit UTC offset.

    Accepts 'Z' or '+00:00'. Rejects naive timestamps and non-zero offsets so
    that every stored time is unambiguously UTC.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{field} is required")
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        text = value.strip()
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            raise ValidationError(f"{field} is not a valid ISO-8601 timestamp: {value!r}") from None
    else:
        raise ValidationError(f"{field} must be an ISO-8601 string or datetime")
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValidationError(f"{field} must include a UTC offset (e.g. 'Z')")
    if dt.utcoffset().total_seconds() != 0:
        raise ValidationError(f"{field} must be in UTC (offset 'Z' or '+00:00')")
    return dt.astimezone(timezone.utc)


def _require_id(value: Optional[str], field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    return value.strip()


def overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    """Half-open interval overlap: [a_start, a_end) vs [b_start, b_end)."""
    return a_start < b_end and b_start < a_end


class AppointmentService:
    """In-memory booking service.

    A single lock serialises the check-then-insert of booking and the
    read-modify-write of cancellation, so concurrent callers cannot both
    pass the conflict check for the same slot.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_id: Dict[str, Appointment] = {}
        self._by_provider: Dict[str, List[str]] = {}

    def book(self, provider_id: str, start: TimeInput, end: TimeInput) -> Appointment:
        # Validate everything before touching shared state.
        pid = _require_id(provider_id, "provider_id")
        s = parse_utc(start, "start")
        e = parse_utc(end, "end")
        if e <= s:
            raise ValidationError("end must be after start (duration must be positive)")

        with self._lock:
            for appt_id in self._by_provider.get(pid, []):
                other = self._by_id[appt_id]
                if other.status is Status.ACTIVE and overlaps(s, e, other.start, other.end):
                    raise ConflictError(
                        f"provider {pid} already has appointment {other.id} "
                        f"from {other.start.isoformat()} to {other.end.isoformat()}",
                        conflicting_id=other.id,
                    )
            appt = Appointment(id=str(uuid.uuid4()), provider_id=pid, start=s, end=e)
            self._by_id[appt.id] = appt
            self._by_provider.setdefault(pid, []).append(appt.id)
            return appt

    def cancel(self, appointment_id: str) -> CancelResult:
        aid = _require_id(appointment_id, "appointment_id")
        with self._lock:
            appt = self._by_id.get(aid)
            if appt is None:
                return CancelResult(CancelOutcome.NOT_FOUND)
            if appt.status is Status.CANCELLED:
                return CancelResult(CancelOutcome.ALREADY_CANCELLED, appt)
            cancelled = replace(appt, status=Status.CANCELLED)
            self._by_id[aid] = cancelled
            return CancelResult(CancelOutcome.CANCELLED, cancelled)

    def get(self, appointment_id: str) -> Optional[Appointment]:
        with self._lock:
            return self._by_id.get(appointment_id)

    def list_for_provider(self, provider_id: str, include_cancelled: bool = False) -> List[Appointment]:
        with self._lock:
            appts = [self._by_id[i] for i in self._by_provider.get(provider_id, [])]
        if not include_cancelled:
            appts = [a for a in appts if a.status is Status.ACTIVE]
        return sorted(appts, key=lambda a: a.start)
