# Findings

A one-page summary of the results. Details are in [DESIGN.md](DESIGN.md), [NOTES.md](NOTES.md) and [AI_USE_RECORD.md](AI_USE_RECORD.md).

## 1. Acceptance criteria: status

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | A valid booking with a positive duration succeeds | ✅ | `test_book_valid_appointment`, `test_accepts_plus_zero_offset_and_datetime` |
| 2 | An overlap for the same provider is rejected; different providers don't conflict | ✅ | `test_same_provider_overlap_rejected` (5 overlap shapes), `test_different_providers_do_not_conflict` |
| 3 | Back-to-back (touching) appointments are allowed | ✅ | `test_adjacent_appointments_allowed`, `test_one_microsecond_overlap_rejected` |
| 4 | Cancelling frees the slot; cancelling a missing or already-cancelled booking gives a clear result | ✅ | `test_cancelled_appointment_frees_slot`, `test_cancel_missing_returns_not_found`, `test_cancel_twice_returns_already_cancelled` |
| 5 | Invalid input is rejected without changing stored bookings | ✅ | `test_invalid_booking_rejected_without_state_change` (12 cases, before/after snapshot), `test_cancel_with_missing_id_rejected` |
| 6 | Tests cover every case, plus concurrency | ✅ | 34 tests; 2 concurrency tests (50 threads on the same slot; 40 threads on overlapping slots) |
| 7 | AI use recorded | ✅ | [AI_USE_RECORD.md](AI_USE_RECORD.md) |

## 2. Test results

```
$ python -m pytest -q
34 passed
```

## 3. Mutation testing: do the tests catch real bugs?

| Deliberate bug | Result |
|---|---|
| Removed the lock and added a 1 ms delay between check and insert | Both concurrency tests **failed**, so the race is detected |
| Changed the overlap test `<` to `<=` (touching appointments counted as overlapping) | Back-to-back tests **failed**, so the boundary is protected |

## 4. Key findings and decisions

1. **Half-open intervals `[start, end)` are what make back-to-back bookings work.** The overlap test is `a.start < b.end and b.start < a.end`. Using `<=` would wrongly reject them, and the mutation test confirms this.
2. **Checking and then booking must happen as one locked step.** Without a lock, two simultaneous requests can both pass the check and double-book. This was shown by the mutation test.
3. **Validate before taking the lock.** Invalid input is rejected before any stored data is touched, so bad requests can never change stored bookings.
4. **Timestamps with no offset are rejected, not assumed to be UTC.** Silently treating local time as UTC would book the wrong slot without any error, which is worse than rejecting the request.
5. **Cancelling returns a result instead of raising an error.** `NOT_FOUND` and `ALREADY_CANCELLED` are expected outcomes, and returning them makes cancel safe to retry.

## 5. Risks discovered (within scope)

- The in-memory lock does not protect multiple processes. Moving to a database needs a database-level constraint, such as a PostgreSQL `EXCLUDE USING gist`.
- No idempotency key: a retried booking request conflicts with its own earlier booking.
- Rescheduling means cancel then book, and someone else can take the slot in between.
- The conflict scan costs O(n) per provider, and cancelled records are kept forever.

See [NOTES.md](NOTES.md) for the full list.

## 6. AI contribution (summary)

AI (Claude) was used to break down the requirements, design the service, write the code and tests, and draft the documents. Three AI suggestions were rejected or edited:

- treating timestamps with no offset as UTC (rejected)
- converting non-UTC offsets (rejected)
- having cancel raise an error (edited to return a result)

All changes were verified by the test suite and the mutation checks above. Full record: [AI_USE_RECORD.md](AI_USE_RECORD.md).
