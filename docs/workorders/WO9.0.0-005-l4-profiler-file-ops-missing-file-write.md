# WO9.0.0-005 — Sandbox: L4 profiler _FILE_OPS missing file_write/file_open — seccomp_trace events skipped (WO8-009 incomplete)

**Series:** WO9.0.0 (audit round 2026-08-23)
**Status:** OPEN
**Owner:** (unassigned)
**Priority:** P1 · Effort M · Risk M
**Scope:** `picosentry/sandbox/l4/profiler.py`, `picosentry/sandbox/l3/backends/seccomp_trace/event_parser.py`, `picosentry/sandbox/l3/backends/seccomp_trace/orchestrator.py`, `tests/sandbox/`

**Gate:** `bash scripts/test.sh fast` + test: a seccomp_trace `file_write` event with a path produces a `FileOperation` with `operation="write"` (not skipped); a `file_open` event with `O_CREAT` flag produces `operation="create"`.

## Objective
WO8-009 added rich file operation types to `_FILE_OP_MAP` (`file_create`→`create`, `file_delete`→`delete`, `file_chmod`→`chmod`, `file_chown`→`chown`), but NO backend ever emits these event types. The seccomp_trace backend emits `file_write` (from `classify_syscall` mapping all `FS_WRITE_SYSCALLS` to `"file_write"`) and `file_open` (from `_OPEN_SYSCALLS`), but `_FILE_OPS` does NOT include `file_write` or `file_open`. So ALL seccomp_trace file events are skipped by `_extract_fs_from_events`, and the profiler falls through to the stdout regex fallback.

Additionally, the seccomp_trace backend's events carry `path=""` (SCMP_ACT_LOG v2.0.8 limitation — documented at orchestrator.py:248), so even if `file_write` were in `_FILE_OPS`, the `not ev.path` guard at profiler.py:84 would skip them. The only path-carrying events are from the subprocess backend's `_check_file_write` (which emits `file_write_indicator`, `file_write_bytes`, `file_save`, `file_export`).

The net effect: on real enforcement backends (seccomp-bpf, seccomp-trace, landlock), the L4 profiler's file-operation extraction from events is dead — it always falls through to stdout regex. The WO8-009 fix (rich `_FILE_OP_MAP`) only helps the subprocess backend, which is the observational-only/degraded path.

## Evidence (verified 2026-08-23, read-only explorer; live repro + grep)
- `profiler.py:25-37`: `_FILE_OPS = frozenset({"file_write_indicator", "file_write_bytes", "file_save", "file_export", "file_read", "file_create", "file_delete", "file_chmod", "file_chown"})` — does NOT include `file_write` or `file_open`.
- `profiler.py:84`: `if ev.operation not in _FILE_OPS or not ev.path:` — seccomp_trace events with `operation="file_write"` are skipped (not in `_FILE_OPS`).
- `event_parser.py:30-36`: `classify_syscall` returns `("file_open", ...)` for `_OPEN_SYSCALLS`, `("file_read", ...)` for `FS_READ_SYSCALLS`, `("file_write", ...)` for `FS_WRITE_SYSCALLS` — seccomp_trace emits `file_write`/`file_open`, not `file_write_indicator`/`file_save`/etc.
- `_seccomp_common.py:44-80`: `FS_WRITE_SYSCALLS` includes `chmod`, `fchmod`, `fchmodat`, `chown`, `mkdir`, `rmdir`, `unlink`, `rename`, `symlink`, `mount` — ALL map to `"file_write"` via `classify_syscall`.
- grep for `file_create`/`file_delete`/`file_chmod`/`file_chown` in backends: no results — NO backend emits these event types.
- `orchestrator.py:248`: `"seccomp-trace: %d events captured, 0 paths/addresses (v2.0.8 SCMP_ACT_LOG limitation)"` — seccomp_trace events have no paths.
- Live repro (python3 in /tmp/opencode): seccomp_trace events with `operation="file_write"` and `path="/tmp/test"` → `_extract_fs_from_events` returns `[]` (0 fs_ops). Even with paths set, `file_write` is not in `_FILE_OPS` so it's skipped.

## Deliverables
1. Add `file_write` and `file_open` to `_FILE_OPS`. Map `file_write`→`"write"`, `file_open`→`"read"` (open without O_CREAT is a read; with O_CREAT it's a create — but the event doesn't carry flags, so default to `"read"` and let the stdout regex add create/write).
2. For seccomp_trace events (which carry no paths), the event-based extraction is still limited — document that the stdout regex fallback is the primary source on seccomp_trace, and the event-based path is for future backends that capture args. Consider parsing the strace-style stdout for chmod/create/delete to populate rich ops on the subprocess backend (which the stdout regex `_extract_file_operations` already does).
3. Regression test: a `file_write` event WITH a path produces a `FileOperation(operation="write")`; a `file_open` event WITH a path produces `operation="read"`.