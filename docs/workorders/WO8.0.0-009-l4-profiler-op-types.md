# WO8.0.0-009 — Sandbox: L4 profiler only emits "read"/"write" ops, making create/delete/chmod rules dead on real backends

**Series:** WO8.0.0 (exploration round 2026-08-22)
**Status:** OPEN
**Owner:** (unassigned — worktree `wo/8.0.0/l4-profiler-op-types`)
**Priority:** P0 · Effort M · Risk M
**Scope:** `picosentry/sandbox/l4/profiler.py`, `picosentry/sandbox/l4/rules/privilege_escalation.py`, `picosentry/sandbox/l4/rules/filesystem.py`, `picosentry/sandbox/l4/rules/persistence.py`, `tests/sandbox/`

**Gate:** `bash scripts/test.sh fast` + test: with event-based profiling, a `file_write_indicator` event to `/etc/cron.d/evil` produces a `FileOperation` with `operation="create"` (not `"write"`); a chmod event produces `operation="chmod"`.

## Objective
The L4 profiler's `_extract_fs_from_events()` (profiler.py:64-65) only produces `operation="read"` or `operation="write"` for ALL kernel events — it binary-splits on `ev.operation == "file_read"`. Multiple L4 rules check for `"create"`, `"delete"`, `"chmod"`, `"chown"` operations, which are NEVER produced from events. On real sandbox backends (seccomp/landlock with kernel events), these rules are dead code:
- `privilege_escalation.py:71`: `if op.operation == "chmod"` — L4-PRIVESC-003 (setuid chmod detection) NEVER fires from events.
- `privilege_escalation.py:43`: `op.operation not in ("write", "create", "chmod", "chown", "delete")` — L4-PRIVESC-001 partially dead (only "write" path works).
- `privilege_escalation.py:102`: `op.operation in ("write", "create")` — L4-PRIVESC-005 (cron manipulation) partially dead.
- `filesystem.py:98`: `if op.operation == "delete"` — L4-FS-003 (critical file deletion) NEVER fires from events.
- `filesystem.py:62,75`: `op.operation in ("write", "create")` — L4-FS-001/002 partially dead (only "write" works).
- `persistence.py:33`: `op.operation not in ("write", "create", "chmod", "chown")` — L4-PERSIST-001 partially dead.

The stdout-based fallback parser (`_extract_file_operations`) DOES produce "create", "delete", "chmod" — so these rules work on the subprocess backend but NOT on real enforcement backends.

## Evidence (verified 2026-08-22, read-only explorer; file:line chain)
- `profiler.py:64-65`: `op_type = "read" if ev.operation == "file_read" else "write"` — only two values ever produced from events.
- `_FILE_OPS` (profiler.py:21): `{"file_write_indicator", "file_write_bytes", "file_save", "file_export", "file_read"}` — all non-read ops map to "write".
- `profiler.py:295-340`: `_extract_file_operations` (stdout fallback) produces "read", "write", "create", "delete", "chmod" — so rules work on subprocess backend only.
- `profiler.py:97-101`: `fs_ops = _extract_fs_from_events(result.events) or _extract_file_operations(combined)` — when events exist (real backend), the event parser wins and only read/write are produced.
- `privilege_escalation.py:70-83`: L4-PRIVESC-003 `if op.operation == "chmod"` — dead on events.
- `filesystem.py:98-109`: L4-FS-003 `if op.operation == "delete"` — dead on events.
- `filesystem.py:122-123`: `if op.operation == "chmod" and "path" in op.path.lower(): pass` — acknowledged dead code (comment says "skip for now").

## Deliverables
1. Map event operations to richer `FileOperation.operation` values: `file_save`/`file_export` -> `"create"`, `file_write_bytes` with a new path -> `"create"`, add a `file_chmod`/`file_chown` event type (or derive from sandbox event details). At minimum, distinguish "create" (new file) from "write" (modify existing) based on event semantics.
2. Regression test: feed a `file_save` event to `/etc/cron.d/evil` and assert `FileOperation.operation == "create"`; feed a chmod event and assert `operation == "chmod"`.