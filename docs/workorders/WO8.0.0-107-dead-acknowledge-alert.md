# WO8.0.0-107 — Serve: dead `EnhancedOrchestrator.acknowledge_alert` still sets `sent=1` (WO7-028 regression risk)

**Series:** WO8.0.0 (exploration round 2026-08-22)
**Status:** OPEN
**Owner:** (unassigned)
**Priority:** P2 · Effort S · Risk L
**Scope:** `picosentry/serve/services/orchestrator.py`, `tests/serve/`

**Gate:** `bash scripts/test.sh fast` + test: no method named `acknowledge_alert` on `EnhancedOrchestrator` (dead code removed).

## Objective
WO7-028 added a separate `acknowledged` column to the `alerts` table and changed the live API endpoint (`projects.py:200-218`) to set `acknowledged = 1` instead of `sent = 1`. However, `EnhancedOrchestrator.acknowledge_alert` (orchestrator.py:604-613) still uses the old `sent = 1` pattern. This method has zero callers (confirmed by impact analysis) — it is dead code. If anyone wires it up, they reintroduce the WO7-028 bug (conflating "acknowledged" with "delivered").

## Evidence (verified 2026-08-22, explorer; file:line chain)
- `orchestrator.py:604-613`: `def acknowledge_alert(self, alert_id: int) -> bool:` — `UPDATE alerts SET sent = 1 WHERE id = ?` (old pattern).
- `projects.py:200-218`: live API endpoint uses `UPDATE alerts SET acknowledged = 1 WHERE id = ?` (new pattern, WO7-028).
- Impact analysis: `acknowledge_alert` (Method) has 0 upstream callers — confirmed dead code.

## Deliverables
1. Delete `EnhancedOrchestrator.acknowledge_alert` (dead code, regression risk).
2. Regression test per the gate.