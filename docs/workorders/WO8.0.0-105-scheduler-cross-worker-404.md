# WO8.0.0-105 — Serve: `_assert_job_in_org` checks in-memory dict only → 404 for cross-worker jobs

**Series:** WO8.0.0 (exploration round 2026-08-22)
**Status:** OPEN
**Owner:** (unassigned)
**Priority:** P1 · Effort S · Risk M
**Scope:** `picosentry/serve/api/routers/scheduler.py`, `picosentry/serve/services/scheduler.py`, `tests/serve/`

**Gate:** `bash scripts/test.sh fast` + test: a job created on worker A can be enabled/disabled/triggered/deleted via worker B's API before `_converge_jobs` runs.

## Objective
`_assert_job_in_org` checks `scheduler.jobs.get(job_id)` — the in-memory dict. In multi-worker mode, a job created on worker A is not in worker B's in-memory dict until `_converge_jobs` reloads from the DB (every 30s). In that window, enable/disable/trigger/delete return 404 from worker B even though the job exists in the shared DB. The documented multi-worker ceiling says "a removed/disabled job can fire once more if a standby takes over" — but this is worse: jobs are invisible to CRUD operations on non-leader workers, not just to the scheduler loop.

## Evidence (verified 2026-08-22, explorer; file:line chain)
- `scheduler.py:129-131`: `_assert_job_in_org` reads `scheduler.jobs.get(job_id)` — in-memory only.
- `scheduler.py:114-129`: `_load_jobs` loads from DB at boot; `_converge_jobs` reloads every `reload_every` (30s default, `scheduler.py:634`).
- `scheduler.py:615-630`: `_converge_jobs` runs only on the leader (`scheduler.py:662-666`). Non-leader workers never converge — their `jobs` dict is only refreshed on leadership transition (`_reschedule_all`, `scheduler.py:594-613`).
- Impact: `enable_job` (`scheduler.py:240`), `disable_job` (`scheduler.py:251`), `remove_job` (`scheduler.py:229`), `trigger_job` (`scheduler.py:289`), `update_job` (`scheduler.py:262`) all check `self.jobs.get(job_id)` — same in-memory-only check.

## Deliverables
1. `_assert_job_in_org` should fall back to a DB lookup (`SELECT org_id FROM scheduled_jobs WHERE id = ?`) when the job is not in the in-memory dict.
2. `enable_job`/`disable_job`/`remove_job`/`trigger_job`/`update_job` should also handle the case where the job is in the DB but not in memory (reload from DB on miss).
3. Regression test per the gate.