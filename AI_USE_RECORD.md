# AI Prompt and Use Record

**AI tool:** Claude (Anthropic), Opus 5.5, chat with a code sandbox.
**Date:** 2026-11-23
**Sensitive data:** No credentials, secrets or personal data were included in any prompt. The only material shared was the assessment brief (PDF).

> **Candid summary:** AI was used for requirement breakdown, design, implementation, test writing and the first draft of the documents. The candidate's own review and verification steps are recorded in §3. Before submitting, complete the "Candidate review" rows in §3 with what *you* checked or changed.

---

## 1. Prompts used

| # | Prompt (verbatim) | Engineering activity |
|---|---|---|
| P1 | *[Attached assessment PDF]* "List of tasks to be performed" | Requirement analysis and breaking the work into tasks |
| P2 | "Yes" (accepting the AI's offer to build a small Python service with an in-memory store, tests and the documents) | Design, implementation, tests, documents |

*Add any later prompts (for example, asking for review or changes) as P3, P4 and so on.*

## 2. AI responses, and what was accepted, edited or rejected

| Ref | AI output (summary) | Decision | Files / decisions it informed |
|---|---|---|---|
| P1 | Turned the brief into 6 task groups: set up, build the feature, tests, AI record, documents, submit. Proposed the half-open overlap test `newStart < existingEnd && existingStart < newEnd` as the way to allow back-to-back bookings. | **Accepted** | Task plan; overlap rule in `service.overlaps()` |
| P2-a | Chose Python with the standard library only and a CLI fallback, since no starter project was supplied. | **Accepted** | Project structure |
| P2-b | Treat timestamps with no offset as UTC. | **Rejected** by the AI while designing: it would silently book local times as UTC. Replaced with *reject anything without an explicit `Z` or `+00:00`*. | `parse_utc()`; DESIGN §7 |
| P2-c | Convert non-UTC offsets to UTC. | **Rejected** in favour of rejecting them, as a stricter reading of "keep time-zone handling to UTC" (easy to relax later). | `parse_utc()`; NOTES limitations |
| P2-d | Make cancelling a missing or already-cancelled appointment raise an exception. | **Edited**: changed to return a `CancelResult` with outcome `NOT_FOUND` or `ALREADY_CANCELLED`. These are expected outcomes, and returning a result makes cancel safe to retry. A blank ID still raises `ValidationError`. | `cancel()`; DESIGN §3 |
| P2-e | Use one `threading.Lock` around check-then-insert and around cancel. Validate *before* taking the lock. | **Accepted** | `AppointmentService`; DESIGN §5–6 |
| P2-f | Test suite: 34 tests across all criteria, including parametrised overlap shapes, 12 kinds of invalid input with before/after store snapshots, a 1 µs overlap edge case, and two concurrency tests. | **Accepted** | `tests/test_service.py`, `tests/test_cli.py` |
| P2-g | First drafts of README, DESIGN, NOTES and this record. | **Accepted as drafts**; the candidate must review them | `*.md` |

## 3. Verification evidence

### 3.1 Automated tests

```
$ python -m pytest -q
..................................                                       [100%]
34 passed in 0.08s
```

### 3.2 Mutation checks (do the tests catch real bugs?)

| Deliberate bug | Expected | Observed |
|---|---|---|
| Removed the lock in `book()` and added a 1 ms delay between check and insert | Concurrency tests fail | `test_concurrent_bookings_for_same_slot_only_one_wins` and `test_concurrent_overlapping_ranges_preserve_invariant` **FAILED** (2 failed) |
| Changed the overlap test from `<` to `<=`, so touching appointments counted as overlapping | Back-to-back tests fail | `test_adjacent_appointments_allowed` and `test_accepts_plus_zero_offset_and_datetime` **FAILED** (3 failed in total) |

Both bugs were caught, so the tests are not passing by accident.

### 3.3 Manual CLI run

```
book dr-1 2026-12-01T09:00:00Z 2026-12-01T09:30:00Z  -> BOOKED ...
book dr-1 2026-12-01T09:15:00Z 2026-12-01T09:45:00Z  -> ERROR CONFLICT ...
book dr-1 2026-12-01T09:30:00Z 2026-12-01T10:00:00Z  -> BOOKED ...   (back-to-back allowed)
book dr-1 2026-12-01T10:00:00Z 2026-12-01T10:00:00Z  -> ERROR INVALID_INPUT: end must be after start
```

### 3.4 Candidate review (complete before submitting)

| Check | Done? | Notes / changes made |
|---|---|---|
| Read `service.py` line by line; confirmed the overlap test and the lock scope | ☐ | |
| Ran `python -m pytest -v` locally | ☐ | |
| Repeated at least one mutation check | ☐ | |
| Worked one overlap case out by hand (for example 09:00–09:30 vs 09:30–10:00) | ☐ | |
| Reviewed the assumptions in NOTES.md and agreed or changed them | ☐ | |
