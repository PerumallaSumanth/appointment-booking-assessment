# Notes: Assumptions, Booking Invariant, Limitations

## Booking invariant

No provider ever has two ACTIVE appointments whose half-open intervals `[start, end)` overlap. Touching intervals, where one ends exactly when the next starts, are allowed. Cancelled appointments never block a booking.

## Assumptions

1. No starter project was supplied, so the work uses the in-memory service and CLI fallback. Data lasts only as long as the process runs.
2. All timestamps are UTC and must include an explicit `Z` or `+00:00`. Timestamps with no offset, or with any other offset, are rejected.
3. The end time is exclusive, and the duration must be at least one microsecond.
4. Provider IDs are opaque strings. The service does not check that a provider exists, because there is no provider registry in scope. Surrounding whitespace is trimmed.
5. Appointments are identified by service-generated UUIDs.
6. Cancellation is a soft delete. Cancelling a missing appointment returns `NOT_FOUND`; cancelling an already-cancelled one returns `ALREADY_CANCELLED`. Neither raises an exception.
7. There are no business rules about past dates, maximum length or working hours. A booking in the past is accepted.
8. Clients and patients are not modelled. A client double-booking themselves across different providers is not checked.

## Limitations and follow-up risks

- **No persistence.** All data is lost on restart. A real deployment needs the rule enforced in the database (for example a PostgreSQL exclusion constraint on `tstzrange(start, end, '[)')` where status is ACTIVE). Checking in application code alone is not safe across several processes.
- **The lock only works within one process.** `threading.Lock` does not protect multiple workers or hosts.
- **Linear conflict scan.** Each booking costs O(number of that provider's appointments). A provider with a long history would slow down. An index by time, or ignoring past appointments, would fix this.
- **Cancelled records are kept forever.** Memory grows without limit. A cleanup or archive rule would be needed.
- **No idempotency on booking.** If a client retries a timed-out request, it gets `CONFLICT` against its own earlier booking rather than the original result. An idempotency key would fix this.
- **Strict UTC rule.** Clients that send `+05:30` are rejected. If product wants to accept such times, the change belongs in `parse_utc` (convert instead of rejecting), and the tests that expect rejection must be updated.
- **No reschedule operation.** Moving an appointment means cancelling and then booking. Between the two calls, someone else can take the slot. A single atomic `reschedule` would remove that gap.
- **Daylight saving time.** Not a problem while everything is stored in UTC, but it will matter once any local-time input or display is added.
