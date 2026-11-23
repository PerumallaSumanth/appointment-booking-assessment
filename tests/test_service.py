import threading
from datetime import datetime, timedelta, timezone

import pytest

from scheduler import (
    AppointmentService,
    CancelOutcome,
    ConflictError,
    Status,
    ValidationError,
)


@pytest.fixture
def svc():
    return AppointmentService()


def snapshot(svc, *providers):
    return {p: svc.list_for_provider(p, include_cancelled=True) for p in providers}


# --- AC1: successful booking -------------------------------------------------

def test_book_valid_appointment(svc):
    appt = svc.book("dr-1", "2026-12-01T09:00:00Z", "2026-12-01T09:30:00Z")
    assert appt.provider_id == "dr-1"
    assert appt.status is Status.ACTIVE
    assert appt.start == datetime(2026, 12, 1, 9, 0, tzinfo=timezone.utc)
    assert appt.end - appt.start == timedelta(minutes=30)
    assert svc.get(appt.id) == appt


def test_accepts_plus_zero_offset_and_datetime(svc):
    svc.book("dr-1", "2026-12-01T09:00:00+00:00", "2026-12-01T10:00:00+00:00")
    svc.book("dr-1",
             datetime(2026, 12, 1, 10, tzinfo=timezone.utc),
             datetime(2026, 12, 1, 11, tzinfo=timezone.utc))
    assert len(svc.list_for_provider("dr-1")) == 2


# --- AC2: same-provider overlap / different providers -------------------------

@pytest.mark.parametrize("start,end", [
    ("2026-12-01T09:15:00Z", "2026-12-01T09:45:00Z"),  # partial overlap at the end
    ("2026-12-01T08:45:00Z", "2026-12-01T09:15:00Z"),  # partial overlap at the start
    ("2026-12-01T09:10:00Z", "2026-12-01T09:20:00Z"),  # fully inside
    ("2026-12-01T08:00:00Z", "2026-12-01T10:00:00Z"),  # fully covers
    ("2026-12-01T09:00:00Z", "2026-12-01T09:30:00Z"),  # identical
])
def test_same_provider_overlap_rejected(svc, start, end):
    first = svc.book("dr-1", "2026-12-01T09:00:00Z", "2026-12-01T09:30:00Z")
    before = snapshot(svc, "dr-1")
    with pytest.raises(ConflictError) as exc:
        svc.book("dr-1", start, end)
    assert exc.value.conflicting_id == first.id
    assert snapshot(svc, "dr-1") == before


def test_different_providers_do_not_conflict(svc):
    svc.book("dr-1", "2026-12-01T09:00:00Z", "2026-12-01T09:30:00Z")
    other = svc.book("dr-2", "2026-12-01T09:00:00Z", "2026-12-01T09:30:00Z")
    assert other.status is Status.ACTIVE
    assert len(svc.list_for_provider("dr-1")) == 1
    assert len(svc.list_for_provider("dr-2")) == 1


# --- AC3: adjacency -----------------------------------------------------------

def test_adjacent_appointments_allowed(svc):
    svc.book("dr-1", "2026-12-01T09:00:00Z", "2026-12-01T09:30:00Z")
    svc.book("dr-1", "2026-12-01T09:30:00Z", "2026-12-01T10:00:00Z")  # starts at end
    svc.book("dr-1", "2026-12-01T08:30:00Z", "2026-12-01T09:00:00Z")  # ends at start
    assert len(svc.list_for_provider("dr-1")) == 3


def test_one_microsecond_overlap_rejected(svc):
    svc.book("dr-1", "2026-12-01T09:00:00Z", "2026-12-01T09:30:00Z")
    with pytest.raises(ConflictError):
        svc.book("dr-1", "2026-12-01T09:29:59.999999Z", "2026-12-01T10:00:00Z")


# --- AC4: cancellation ---------------------------------------------------------

def test_cancelled_appointment_frees_slot(svc):
    first = svc.book("dr-1", "2026-12-01T09:00:00Z", "2026-12-01T09:30:00Z")
    result = svc.cancel(first.id)
    assert result.outcome is CancelOutcome.CANCELLED and result.ok
    assert svc.get(first.id).status is Status.CANCELLED
    again = svc.book("dr-1", "2026-12-01T09:00:00Z", "2026-12-01T09:30:00Z")
    assert again.id != first.id


def test_cancel_missing_returns_not_found(svc):
    result = svc.cancel("does-not-exist")
    assert result.outcome is CancelOutcome.NOT_FOUND
    assert not result.ok


def test_cancel_twice_returns_already_cancelled(svc):
    appt = svc.book("dr-1", "2026-12-01T09:00:00Z", "2026-12-01T09:30:00Z")
    svc.cancel(appt.id)
    result = svc.cancel(appt.id)
    assert result.outcome is CancelOutcome.ALREADY_CANCELLED
    assert result.appointment.status is Status.CANCELLED


def test_cancel_does_not_free_a_different_overlapping_booking(svc):
    a = svc.book("dr-1", "2026-12-01T09:00:00Z", "2026-12-01T10:00:00Z")
    svc.cancel(a.id)
    svc.book("dr-1", "2026-12-01T09:30:00Z", "2026-12-01T10:30:00Z")
    with pytest.raises(ConflictError):
        svc.book("dr-1", "2026-12-01T09:00:00Z", "2026-12-01T10:00:00Z")


# --- AC5: invalid input leaves state unchanged ---------------------------------

@pytest.mark.parametrize("provider,start,end", [
    ("", "2026-12-01T09:00:00Z", "2026-12-01T09:30:00Z"),          # empty provider
    ("   ", "2026-12-01T09:00:00Z", "2026-12-01T09:30:00Z"),       # blank provider
    (None, "2026-12-01T09:00:00Z", "2026-12-01T09:30:00Z"),        # missing provider
    ("dr-1", None, "2026-12-01T09:30:00Z"),                         # missing start
    ("dr-1", "2026-12-01T09:00:00Z", ""),                           # missing end
    ("dr-1", "not-a-date", "2026-12-01T09:30:00Z"),                 # garbage
    ("dr-1", "2026-13-01T09:00:00Z", "2026-12-01T09:30:00Z"),       # month 13
    ("dr-1", "2026-12-01T09:00:00", "2026-12-01T09:30:00"),         # naive (no offset)
    ("dr-1", "2026-12-01T09:00:00+05:30", "2026-12-01T09:30:00+05:30"),  # non-UTC
    ("dr-1", "2026-12-01T09:30:00Z", "2026-12-01T09:30:00Z"),       # zero duration
    ("dr-1", "2026-12-01T10:00:00Z", "2026-12-01T09:30:00Z"),       # negative duration
    ("dr-1", 12345, "2026-12-01T09:30:00Z"),                        # wrong type
])
def test_invalid_booking_rejected_without_state_change(svc, provider, start, end):
    svc.book("dr-1", "2026-12-02T09:00:00Z", "2026-12-02T09:30:00Z")
    before = snapshot(svc, "dr-1")
    with pytest.raises(ValidationError):
        svc.book(provider, start, end)
    assert snapshot(svc, "dr-1") == before


@pytest.mark.parametrize("bad_id", ["", "  ", None])
def test_cancel_with_missing_id_rejected(svc, bad_id):
    appt = svc.book("dr-1", "2026-12-01T09:00:00Z", "2026-12-01T09:30:00Z")
    with pytest.raises(ValidationError):
        svc.cancel(bad_id)
    assert svc.get(appt.id).status is Status.ACTIVE


# --- AC6: concurrency ---------------------------------------------------------

def test_concurrent_bookings_for_same_slot_only_one_wins(svc):
    n = 50
    barrier = threading.Barrier(n)
    wins, conflicts, errors = [], [], []

    def worker():
        barrier.wait()
        try:
            wins.append(svc.book("dr-1", "2026-12-01T09:00:00Z", "2026-12-01T09:30:00Z"))
        except ConflictError:
            conflicts.append(1)
        except Exception as exc:  # pragma: no cover - surfaced by assertion
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert len(wins) == 1
    assert len(conflicts) == n - 1
    assert len(svc.list_for_provider("dr-1")) == 1


def test_concurrent_overlapping_ranges_preserve_invariant(svc):
    # 40 threads each try a 30-minute slot starting every 10 minutes; many overlap.
    base = datetime(2026, 12, 1, 9, tzinfo=timezone.utc)
    n = 40
    barrier = threading.Barrier(n)

    def worker(i):
        barrier.wait()
        s = base + timedelta(minutes=10 * (i % 12))
        try:
            svc.book("dr-1", s, s + timedelta(minutes=30))
        except ConflictError:
            pass

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    active = svc.list_for_provider("dr-1")
    assert active, "at least one booking should succeed"
    for a, b in zip(active, active[1:]):
        assert a.end <= b.start, f"overlap between {a} and {b}"
