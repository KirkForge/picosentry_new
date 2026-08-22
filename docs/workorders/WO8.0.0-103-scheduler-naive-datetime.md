# WO8.0.0-103 — Serve: scheduler uses naive `datetime.now()` instead of UTC

**Series:** WO8.0.0 (exploration round 2026-08-22)
**Status:** OPEN
**Owner:** (unassigned)
**Priority:** P1 · Effort S · Risk L
**Scope:** `picosentry/serve/services/scheduler.py`, `tests/serve/`

**Gate:** `bash scripts/test.sh fast` + test: `last_run` and `next_run` timestamps are tz-aware UTC, not naive local time.

## Objective
The scheduler uses naive `datetime.now()` (local timezone) instead of `datetime.now(timezone.utc)` in 5 places. The `last_run` column in `scheduled_jobs` stores local-time timestamps while every other timestamp in the system is UTC. On a server in a non-UTC timezone, cron scheduling and `last_run` display will be off by the timezone offset. The `_get_next_run` cron computation uses naive `datetime.now()` so the next-run delay is computed against local time, not UTC — consistent within the scheduler, but the stored `next_run` in the DB is then compared against UTC-stamped queries elsewhere.

## Evidence (verified 2026-08-22, explorer; file:line chain)
- `scheduler.py:304`: `now = datetime.now()` — in `_get_next_run` fallback (no croniter).
- `scheduler.py:314`: `itr = croniter(cron_expression, datetime.now())` — in `_get_next_run` with croniter.
- `scheduler.py:486`: `now = datetime.now()` — in `_execute_job` success path, stored as `last_run`.
- `scheduler.py:504`: `now = datetime.now()` — in `_execute_job` exception path, stored as `last_run`.
- `scheduler.py:540`: `delay = (next_run - datetime.now()).total_seconds()` — in `_schedule_job`.
- Compare: `orchestrator.py:277` uses `datetime.now(timezone.utc)`, `auth.py:229` uses `datetime.now(timezone.utc)`, `event_bus.py:136` uses `datetime.now(timezone.utc)` — every other service is UTC-consistent.

## Deliverables
1. Replace all 5 `datetime.now()` calls in scheduler.py with `datetime.now(timezone.utc)`.
2. Ensure `_get_next_run` returns tz-aware datetimes (croniter with a tz-aware base returns tz-aware).
3. Regression test per the gate (assert `last_run` is tz-aware UTC after a job executes).