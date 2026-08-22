# WO8.0.0-112 — Deploy: duplicate `annotations:` key in PicoDomeWebhookDeliveryFailures alert (summary lost)

**Series:** WO8.0.0 (exploration round 2026-08-22)
**Status:** OPEN
**Owner:** (unassigned)
**Priority:** P2 · Effort S · Risk L
**Scope:** `deploy/monitoring/picodome-alerts.yaml`

**Gate:** `bash scripts/test.sh fast` + `helm lint` or YAML parse validation: no duplicate keys in the alerts file.

## Objective
The `PicoDomeWebhookDeliveryFailures` alert rule has two `annotations:` keys on the same mapping. YAML spec says duplicate keys are a violation; most parsers take the last value, which means the `summary` annotation is silently lost — the alert fires with a description but no summary line, making it harder to triage in Alertmanager.

## Evidence (verified 2026-08-22, explorer; file:line chain)
- `picodome-alerts.yaml:188`: `annotations:` (first key) with `summary: "PicoDome webhook deliveries are failing"`.
- `picodome-alerts.yaml:189`: `annotations:` (second/duplicate key) with `description: "External webhook notifications are failing..."`.
- YAML duplicate-key behavior: last wins — `summary` is silently dropped.

## Deliverables
1. Merge the two `annotations:` blocks into one with both `summary` and `description`.
2. Regression test per the gate (YAML parse with duplicate-key detection).