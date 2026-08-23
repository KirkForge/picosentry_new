# WO9.0.0-003 — Sandbox: L4-CONTAINER-001 severity escalation broken (string comparison instead of severity order)

**Series:** WO9.0.0 (audit round 2026-08-23)
**Status:** OPEN
**Owner:** (unassigned)
**Priority:** P1 · Effort S · Risk L
**Scope:** `picosentry/sandbox/l4/rules/container_escape.py`, `tests/sandbox/`

**Gate:** `bash scripts/test.sh fast` + test: a write to `/etc/resolv.conf` (MEDIUM) produces an L4-CONTAINER-001 finding with severity `HIGH` (escalated from MEDIUM).

## Objective
L4-CONTAINER-001 has a severity-escalation branch for write/create/delete/chmod operations: if the base severity is below HIGH, escalate to HIGH. But the comparison `final_severity.value < Severity.HIGH.value` compares the STRING values of the Severity enum (`"MEDIUM" < "HIGH"`), not the severity ORDER. String comparison is alphabetical: `"MEDIUM" < "HIGH"` is `False` (M > H), `"LOW" < "HIGH"` is `False` (L > H), `"INFO" < "HIGH"` is `False` (I > H). So the escalation NEVER fires — a write to `/etc/resolv.conf` (MEDIUM), `/etc/hostname` (MEDIUM), `/.dockerenv` (INFO), or `/meta-data` (MEDIUM) stays at MEDIUM/LOW instead of escalating to HIGH.

The `SEVERITY_ORDER` dict exists in `picosentry/_core/models.py` (CRITICAL=0, HIGH=1, MEDIUM=2, LOW=3, INFO=4) for exactly this purpose, but it is not used.

## Evidence (verified 2026-08-23, read-only explorer; live repro)
- `container_escape.py:51-55`: `elif (op.operation in ("write", "create", "delete", "chmod", "chown") and final_severity.value < Severity.HIGH.value): final_severity = Severity.HIGH` — string comparison.
- `_core/models.py:7-16`: `Severity(str, Enum)` with values `"CRITICAL"`, `"HIGH"`, `"MEDIUM"`, `"LOW"`, `"INFO"` — string values, not ordered.
- `_core/models.py:18-24`: `SEVERITY_ORDER: dict[str, int] = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}` — the correct ordering, unused by this rule.
- `ESCAPE_PATHS` (container_escape.py:5-24): `/etc/resolv.conf` is MEDIUM, `/etc/hostname` is MEDIUM, `/.dockerenv` is INFO, `/meta-data` is MEDIUM — all should escalate to HIGH on write.
- Live repro (python3 in /tmp/opencode): `FileOperation(path="/etc/resolv.conf", operation="write")` → L4-CONTAINER-001 severity=MEDIUM (should be HIGH). `FileOperation(path="/etc/hostname", operation="write")` → MEDIUM (should be HIGH). `FileOperation(path="/.dockerenv", operation="write")` → INFO (should be HIGH). String comparison test: `"MEDIUM" < "HIGH" = False`, `"LOW" < "HIGH" = False`, `"INFO" < "HIGH" = False`.

## Deliverables
1. Replace the string comparison with `SEVERITY_ORDER` lookup: `if SEVERITY_ORDER.get(final_severity.value.lower(), 4) < SEVERITY_ORDER.get("high", 1): final_severity = Severity.HIGH`. Or use an integer severity on the enum directly.
2. Regression test: a write to `/etc/resolv.conf` produces L4-CONTAINER-001 with severity `HIGH`.