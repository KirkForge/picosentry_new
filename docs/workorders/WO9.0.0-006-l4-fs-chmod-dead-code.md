# WO9.0.0-006 — Sandbox: L4-FS chmod rule is dead code (filesystem.py:122-123 `pass`)

**Series:** WO9.0.0 (audit round 2026-08-23)
**Status:** OPEN
**Owner:** (unassigned)
**Priority:** P2 · Effort S · Risk L
**Scope:** `picosentry/sandbox/l4/rules/filesystem.py`, `tests/sandbox/`

**Gate:** `bash scripts/test.sh fast` + test: a `FileOperation(path="/etc/passwd", operation="chmod")` produces an L4-FS finding for the chmod (or is explicitly removed as dead code with a comment explaining why L4-PRIVESC-001 covers it).

## Objective
`filesystem.py:122-123` has a dead chmod rule: `if op.operation == "chmod" and "path" in op.path.lower(): pass`. The condition is nonsensical (`"path" in op.path.lower()` checks if the literal string "path" is a substring of the file path) and the body is `pass` — it produces no finding. The comment says "chmod events don't have a separate field; skip for now". This is acknowledged dead code from WO8-009 (which noted it at line 29 of the WO file but did not fix it).

A chmod to `/etc/passwd` or `/etc/shadow` is caught by L4-PRIVESC-001 (privilege_escalation.py:42-55, which includes `chmod` in the operation list and checks against `PRIV_ESC_PATHS`). So the filesystem.py chmod rule is redundant — but it should either be removed (with a comment pointing to L4-PRIVESC-001) or implemented properly (e.g. chmod to protected write paths that aren't in `PRIV_ESC_PATHS`).

## Evidence (verified 2026-08-23, read-only explorer; live repro)
- `filesystem.py:122-123`: `if op.operation == "chmod" and "path" in op.path.lower(): pass` — dead code, produces no finding.
- `filesystem.py:9-23`: `PROTECTED_WRITE_PATHS` includes `/etc/passwd`, `/etc/shadow`, `/etc/sudoers`, `/etc/hosts`, etc.
- `privilege_escalation.py:42-55`: L4-PRIVESC-001 catches `chmod` to `PRIV_ESC_PATHS` (which overlaps with `PROTECTED_WRITE_PATHS`).
- Live repro (python3 in /tmp/opencode): `FileOperation(path="/etc/passwd", operation="chmod")` → `detect_filesystem_anomalies` returns 0 findings. `detect_privilege_escalation` returns 1 finding (L4-PRIVESC-001).

## Deliverables
1. Remove the dead `pass` block at filesystem.py:122-123 and add a comment: `# chmod to protected paths is caught by L4-PRIVESC-001 (privilege_escalation.py)`.
2. OR: implement a proper chmod rule that checks `op.operation == "chmod"` against `PROTECTED_WRITE_PATHS` and produces an L4-FS-005 finding (if there are protected paths NOT in `PRIV_ESC_PATHS` that should be flagged for chmod).
3. Regression test: `FileOperation(path="/etc/passwd", operation="chmod")` produces no L4-FS finding (after removal) OR produces the expected finding (after implementation).