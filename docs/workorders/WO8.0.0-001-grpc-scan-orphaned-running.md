# WO8.0.0-001 — Sandbox: gRPC Scan RPC leaves orphaned "running" jobs on scan failure

**Series:** WO8.0.0 (exploration round 2026-08-22)
**Status:** OPEN
**Owner:** (unassigned — worktree `wo/8.0.0/grpc-scan-orphaned-running`)
**Priority:** P0 · Effort S · Risk M
**Scope:** `picosentry/sandbox/grpc_transport/_servicer.py`, `tests/sandbox/`

**Gate:** `bash scripts/test.sh fast` + test: a gRPC Scan RPC that raises after job creation marks the job `status="failed"` in the store (not left as `"running"`).

## Objective
The gRPC `Scan` servicer adds the job to the store with `status="running"` (line 96) but the `except Exception` block (lines 176-207) never updates the job to `"failed"`. A failed gRPC scan leaves a `"running"` job in the store forever — the HTTP daemon marks failed jobs (handler_routes_post.py:259-273, _run_scan_job:367-375) but the gRPC path does not. `reconcile_on_start` (WO7-018) fixes this on daemon restart, but not during runtime. Under sustained gRPC scan failures the store fills with stale `"running"` jobs that pollute `list_recent` and `count`.

## Evidence (verified 2026-08-22, read-only explorer; file:line chain)
- `_servicer.py:86-98`: job added + `self._job_store.update(job_id, status="running", ...)` — inside a `try/except Exception` that silently logs `job_store add/update failed` and continues.
- `_servicer.py:176-207`: `except Exception as e:` handler logs `SCAN_ERROR`, returns error response, but NEVER calls `self._job_store.update(job_id, status="failed", ...)`.
- Compare `handler_routes_post.py:259-273`: HTTP `except (OSError, RuntimeError)` block calls `self.job_store.update(job_id, status="failed", ...)`.
- Compare `handler_routes_post.py:367-375`: `_run_scan_job` `except BaseException` block calls `self.job_store.update(job_id, status="failed", ...)`.
- WO7-018 added `reconcile_on_start()` to mark stale `"running"` jobs as `"failed"` on daemon boot — but this is a restart-only fix, not a runtime fix.

## Deliverables
1. In the `except Exception` block of `Scan()` (line 176-207), add a `job_store.update(job_id, status="failed", error=..., ...)` call (guarded by `if self._job_store is not None`) so failed gRPC scans are marked failed at runtime, matching the HTTP daemon pattern.
2. Regression test: inject a scan that raises mid-execution (mock the scan engine to throw), assert the job's final status in the store is `"failed"`, not `"running"`.