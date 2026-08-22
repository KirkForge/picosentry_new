# WO8.0.0-111 — Deploy: monitoring alerts only cover picodome, not serve (no picoshogun_* alert rules)

**Series:** WO8.0.0 (exploration round 2026-08-22)
**Status:** OPEN
**Owner:** (unassigned)
**Priority:** P2 · Effort M · Risk L
**Scope:** `deploy/monitoring/`, `deploy/helm/serve/`

**Gate:** `bash scripts/test.sh fast` + test: a `serve-alerts.yaml` file exists with rules for `picoshogun_*` metrics (error rate, latency, audit chain, outbox poller death, dropped events).

## Objective
The monitoring alert rules (`deploy/monitoring/picodome-alerts.yaml`) only define alerts for `picodome_*` metrics (sandbox component). The serve API exposes `picoshogun_*` metrics (`picoshogun_uptime_seconds`, `picoshogun_api_requests_total`, `picoshogun_threat_score`, `picoshogun_outbox_poller_alive`, `picoshogun_dropped_audit_records`, `picoshogun_dropped_correlation_events`, `ws_dropped_messages`) but has ZERO alert rules. A serve-side outage (high error rate, dead outbox poller, dropped audit records) is invisible to Prometheus alerting.

## Evidence (verified 2026-08-22, explorer; file:line chain)
- `deploy/monitoring/picodome-alerts.yaml`: 190 lines, all rules reference `picodome_*` metrics.
- `grep -c "picoshogun\|picosentry" picodome-alerts.yaml` = 0.
- `serve/services/metrics.py`: produces `picoshogun_*` metric names.
- `serve/services/event_bus.py:269`: `metrics.set_global_gauge("picoshogun_outbox_poller_alive", 1.0)` — outbox poller liveness gauge.
- `serve/middleware/audit.py:67`: `metrics.set_global_gauge("dropped_audit_records", self.dropped)` — audit drop gauge.
- `serve/services/correlation/engine.py:97`: `metrics.set_global_gauge("dropped_correlation_events", self.dropped_events)` — correlation drop gauge.
- No `serve-alerts.yaml` or equivalent file exists in `deploy/monitoring/`.

## Deliverables
1. Create `deploy/monitoring/serve-alerts.yaml` with rules for: high error rate (`picoshogun_api_requests_total{status_class="5xx"}`), high latency (`picoshogun_api_request_duration_seconds`), outbox poller death (`picoshogun_outbox_poller_alive == 0`), dropped audit records (`picoshogun_dropped_audit_records > 0`), dropped correlation events (`picoshogun_dropped_correlation_events > 0`), WS dropped messages (`ws_dropped_messages > 0`).
2. Document the serve alert rules in the manual.
3. Regression test per the gate (file existence + rule name check).