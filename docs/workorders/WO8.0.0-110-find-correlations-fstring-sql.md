# WO8.0.0-110 — Serve: `find_correlations` f-string INTERVAL interpolation (fragile SQL pattern)

**Series:** WO8.0.0 (exploration round 2026-08-22)
**Status:** OPEN
**Owner:** (unassigned)
**Priority:** P2 · Effort S · Risk L
**Scope:** `picosentry/serve/services/intelligence.py`, `tests/serve/`

**Gate:** `bash scripts/test.sh fast` + test: `find_correlations` with a non-integer `time_window_hours` (e.g. string "24") raises ValueError before hitting the DB, not a SQL error.

## Objective
`find_correlations` interpolates `time_window_hours` directly into a postgres `INTERVAL` string via f-string. The `int()` cast at line 394 prevents actual SQL injection (an int can't contain SQL), but the pattern is fragile — if the cast is ever removed or the type changes, it becomes injectable. The `date_add_hours` call at line 416 has the same pattern (interpolating the int into the SQL fragment). The sqlite path correctly uses a parameterized `?` placeholder.

## Evidence (verified 2026-08-22, explorer; file:line chain)
- `intelligence.py:394`: `time_window_hours = int(time_window_hours)` — sanitizes to int.
- `intelligence.py:397-398`: `f"i1.created_at BETWEEN i2.created_at - INTERVAL '{time_window_hours} hours' AND i2.created_at + INTERVAL '{time_window_hours} hours'"` — f-string interpolation into SQL.
- `intelligence.py:416`: `db.dialect.date_add_hours("now", -time_window_hours)` — same int interpolation into SQL fragment.
- Compare: sqlite path at line 402 uses `?` placeholder correctly.

## Deliverables
1. Use postgres parameterized intervals: `INTERVAL '%s hours'` with `(time_window_hours,)` as a param, or use `make_interval(hours => %s)` which accepts a parameter.
2. Regression test per the gate.