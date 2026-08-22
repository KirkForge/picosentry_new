# WO8.0.0-109 — Serve: `log_manager.cleanup` uses naive `datetime.now()` (inconsistent with UTC convention)

**Series:** WO8.0.0 (exploration round 2026-08-22)
**Status:** OPEN
**Owner:** (unassigned)
**Priority:** P2 · Effort S · Risk L
**Scope:** `picosentry/serve/services/log_manager.py`, `tests/serve/`

**Gate:** `bash scripts/test.sh fast` + test: log file retention cutoff is UTC, not local time.

## Objective
`log_manager.py:80` uses naive `datetime.now()` for the retention cutoff, while the rest of the system uses UTC. On a non-UTC server, log files are compared against local time but their `st_mtime` is also local (filesystem time), so the comparison is accidentally correct. However, this is inconsistent with the codebase convention and breaks if the container's timezone is set differently from the filesystem's timezone (e.g. a container with `TZ=UTC` running on a host with local time). The `get_stats` method at line 115 also uses `datetime.fromtimestamp` without tz — same issue.

## Evidence (verified 2026-08-22, explorer; file:line chain)
- `log_manager.py:80`: `cutoff = datetime.now() - timedelta(days=self.retention_days)` — naive local time.
- `log_manager.py:85`: `mtime = datetime.fromtimestamp(log_file.stat().st_mtime)` — naive local time from filesystem.
- `log_manager.py:115`: `datetime.fromtimestamp(f.stat().st_mtime).isoformat()` — naive local time.
- Compare: `scheduler.py:40-42` has `_utcnow()` helper, `orchestrator.py:277` uses `datetime.now(timezone.utc)`.

## Deliverables
1. Use `datetime.now(timezone.utc)` for the cutoff in `cleanup()`.
2. Use `datetime.fromtimestamp(ts, tz=timezone.utc)` for `st_mtime` conversions.
3. Regression test per the gate.