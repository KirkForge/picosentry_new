# WO8.0.0-108 — Serve: `pending_alerts` counts `sent=0` (not delivered) instead of `acknowledged=0` (not acknowledged)

**Series:** WO8.0.0 (exploration round 2026-08-22)
**Status:** OPEN
**Owner:** (unassigned)
**Priority:** P2 · Effort S · Risk L
**Scope:** `picosentry/serve/api/routers/dashboard.py`, `picosentry/serve/services/orchestrator.py`, `tests/serve/`

**Gate:** `bash scripts/test.sh fast` + test: dashboard `pending_alerts_count` reflects unacknowledged alerts, not undelivered ones.

## Objective
WO7-028 added a separate `acknowledged` column to `alerts`, making "delivered" (`sent`) and "acknowledged" (`acknowledged`) independent states. But `dashboard.py:39` and `orchestrator.py:147` still count `WHERE sent = 0` for "pending alerts" — this counts alerts that haven't been delivered (e.g. SMTP failure), not alerts awaiting operator acknowledgement. An alert that was successfully delivered (`sent=1`) but not yet acknowledged (`acknowledged=0`) is the one an operator needs to see as "pending" — but it's excluded from the count. Conversely, an undelivered alert (`sent=0`) that was acknowledged (`acknowledged=1`) is counted as pending even though it's been handled.

## Evidence (verified 2026-08-22, explorer; file:line chain)
- `dashboard.py:39`: `pending_alerts = db.execute_one("SELECT COUNT(*) as c FROM alerts WHERE sent = 0 AND org_id = ?", (org["id"],))` — counts undelivered, not unacknowledged.
- `orchestrator.py:147`: `alerts_where = "WHERE sent = 0"` — same pattern in `get_status()`.
- `projects.py:213`: `db.execute_insert("UPDATE alerts SET acknowledged = 1 WHERE id = ?", (alert_id,))` — acknowledge sets `acknowledged`, not `sent`.
- Migration 25 (`_schema.py:1096-1112`): added `acknowledged BOOLEAN DEFAULT 0` column.
- `projects.py:179-197`: `list_alerts` has no `acknowledged` filter — operators can't filter by acknowledgement status.

## Deliverables
1. Change `pending_alerts` count in `dashboard.py` and `orchestrator.py` to `WHERE acknowledged = 0 AND org_id = ?` (or `WHERE sent = 1 AND acknowledged = 0` if "pending" means "delivered but not acknowledged").
2. Add `acknowledged` query parameter to `list_alerts` endpoint so operators can filter by acknowledged/unacknowledged.
3. Regression test per the gate.