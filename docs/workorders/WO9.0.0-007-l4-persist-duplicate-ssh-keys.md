# WO9.0.0-007 — Sandbox: L4-PERSIST-001 duplicate finding for /root/.ssh/authorized_keys

**Series:** WO9.0.0 (audit round 2026-08-23)
**Status:** OPEN
**Owner:** (unassigned)
**Priority:** P2 · Effort S · Risk L
**Scope:** `picosentry/sandbox/l4/rules/persistence.py`, `tests/sandbox/`

**Gate:** `bash scripts/test.sh fast` + test: a write to `/root/.ssh/authorized_keys` produces exactly ONE L4-PERSIST-001 finding (not two).

## Objective
`PERSISTENCE_PATHS` (persistence.py:5-24) includes both `/.ssh/authorized_keys` (line 10) and `/root/.ssh/` (line 12). The matching logic (line 40-45) uses `endswith` for `/.`-prefixed paths and `startswith`/`==` for others. A write to `/root/.ssh/authorized_keys` matches BOTH:
- `/.ssh/authorized_keys` → `op.path.endswith("/.ssh/authorized_keys")` → True (suffix match)
- `/root/.ssh/` → `op.path.startswith("/root/.ssh/")` → True (prefix match)

So the loop at line 35-55 produces TWO L4-PERSIST-001 findings for the same operation — one with description "SSH authorized_keys write" (CRITICAL) and one with "root SSH directory write" (CRITICAL). The duplicate inflates the finding count and the `by_rule` stats.

## Evidence (verified 2026-08-23, read-only explorer; live repro)
- `persistence.py:10`: `("/.ssh/authorized_keys", "SSH authorized_keys write", Severity.CRITICAL)` — suffix match.
- `persistence.py:12`: `("/root/.ssh/", "root SSH directory write", Severity.CRITICAL)` — prefix match.
- `persistence.py:40-45`: suffix matching for `/.`-prefixed paths, prefix/exact for others — both rules fire for `/root/.ssh/authorized_keys`.
- Live repro (python3 in /tmp/opencode): `FileOperation(path="/root/.ssh/authorized_keys", operation="write")` → 2 findings:
  - L4-PERSIST-001: "Persistence path written (write): /root/.ssh/authorized_keys — SSH authorized_keys write"
  - L4-PERSIST-001: "Persistence path written (write): /root/.ssh/authorized_keys — root SSH directory write"

## Deliverables
1. After the first match in the `PERSISTENCE_PATHS` loop, `break` (like `honeypot.py:40` does). This prevents duplicate findings for the same path; the first (most specific) match wins.
2. OR: remove the `/root/.ssh/` entry from `PERSISTENCE_PATHS` since `/.ssh/authorized_keys` (suffix) already covers it, and add `/root/.ssh/config` and `/root/.ssh/known_hosts` explicitly if needed.
3. Regression test: a write to `/root/.ssh/authorized_keys` produces exactly ONE L4-PERSIST-001 finding.