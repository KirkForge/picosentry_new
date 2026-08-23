# WO9.0.0-008 — Sandbox: L4 profiler extracts garbage executable from seccomp_trace process_spawn event detail

**Series:** WO9.0.0 (audit round 2026-08-23)
**Status:** OPEN
**Owner:** (unassigned)
**Priority:** P2 · Effort S · Risk L
**Scope:** `picosentry/sandbox/l4/profiler.py`, `tests/sandbox/`

**Gate:** `bash scripts/test.sh fast` + test: a seccomp_trace `process_spawn` event with `detail="execve syscall (no path/address: SCMP_ACT_LOG does not capture args in v2.0.8)"` produces NO `ProcessSpawn` (not a garbage executable).

## Objective
The seccomp_trace backend emits `process_spawn` events for `execve`/`fork`/`clone` syscalls, but the `detail` field is a generic string: `f"{name} syscall (no path/address: SCMP_ACT_LOG does not capture args in v2.0.8)"` (orchestrator.py:88, event_parser.py:88). The L4 profiler's `_extract_spawns_from_events` (profiler.py:95-107) extracts the executable from `ev.detail.rsplit(":", 1)[-1].strip()`, which produces `"SCMP_ACT_LOG does not capture args in v2.0.8)"` — a garbage string, not a real executable path.

This garbage `ProcessSpawn` inflates `len(profile.spawns)` by 1, which can false-trigger:
- L4-PROC-003 (`if len(profile.spawns) > 10`) — needs 10 real spawns + 1 garbage = 11 to fire.
- L4-SC-004 (`if best[0].expected_spawns == 0 and len(profile.spawns) > 0`) — a zero-spawn baseline with 1 garbage spawn fires.

The dedup `seen` set limits the inflation to +1 (all seccomp_trace events share the same detail suffix), so the impact is small but non-zero.

## Evidence (verified 2026-08-23, read-only explorer; live repro)
- `profiler.py:95-107`: `_extract_spawns_from_events` — `exe = ev.detail.rsplit(":", 1)[-1].strip()` extracts the last `:`-separated segment of the detail string.
- `event_parser.py:88`: `detail=(f"{name} syscall (no path/address: SCMP_ACT_LOG does not capture args in v2.0.8)")` — the detail is a generic string, not the executable path.
- `orchestrator.py:248`: `"0 paths/addresses (v2.0.8 SCMP_ACT_LOG limitation)"` — documented limitation.
- Live repro (python3 in /tmp/opencode): seccomp_trace `process_spawn` event with `detail="execve syscall (no path/address: SCMP_ACT_LOG does not capture args in v2.0.8)"` → `ProcessSpawn(executable="SCMP_ACT_LOG does not capture args in v2.0.8)", args=["SCMP_ACT_LOG does not capture args in v2.0.8)"])`.

## Deliverables
1. In `_extract_spawns_from_events`, skip events where the detail is the generic SCMP_ACT_LOG string (e.g. `if "SCMP_ACT_LOG does not capture args" in ev.detail: continue`), or check that the extracted `exe` looks like a path/command (contains `/` or `.`, or is a known binary name).
2. Regression test: a seccomp_trace `process_spawn` event with the generic detail produces no `ProcessSpawn`.