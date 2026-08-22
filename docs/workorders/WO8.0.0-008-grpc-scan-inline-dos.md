# WO8.0.0-008 — Sandbox: gRPC Scan runs inline on RPC thread (blocks Health, DoS with 10 concurrent scans)

**Series:** WO8.0.0 (exploration round 2026-08-22)
**Status:** OPEN
**Owner:** (unassigned — worktree `wo/8.0.0/grpc-scan-inline-dos`)
**Priority:** P0 · Effort M · Risk M
**Scope:** `picosentry/sandbox/grpc_transport/_servicer.py`, `picosentry/sandbox/grpc_transport/server.py`, `tests/sandbox/`

**Gate:** `bash scripts/test.sh fast` + test: with max_workers=2 and 2 concurrent slow Scan RPCs (mocked to sleep), a Health RPC returns within 1s (not blocked).

## Objective
The gRPC `Scan` RPC runs the sandbox scan + L4 analysis inline on the RPC thread (`_servicer.py:100-111`). The gRPC server uses a single `ThreadPoolExecutor(max_workers=10)` (`server.py:103`) shared by ALL RPCs including Health. A scan holds its thread for the entire scan duration (timeout default 30s, max 300s). With 10 concurrent Scan RPCs (all valid tokens), every thread is busy and the server cannot accept new RPCs — including unauthenticated `Health()` checks. The rate limiter (WO7-015) allows burst=10, exactly matching the thread pool size, so 10 rapid scans from one token exhaust all threads. Compare the HTTP daemon which uses a separate `scan_executor` (`handler_routes_post.py:204-258`) with a `scan_slots` semaphore, freeing the HTTP handler thread immediately.

## Evidence (verified 2026-08-22, read-only explorer; file:line chain)
- `_servicer.py:100-106`: `sandbox_result = self._scan_engine.scan(...)` — inline scan on the RPC thread, blocks for up to `timeout` seconds.
- `_servicer.py:108-111`: `analysis_result = self._scan_engine.analyze(...)` — inline L4 analysis, additional CPU time.
- `server.py:103`: `futures.ThreadPoolExecutor(max_workers=self._max_workers)` — default 10, shared by all RPCs.
- `server.py:104`: `interceptors=[build_auth_interceptor(...)]` — the interceptor runs on the same thread pool.
- `auth.py:140-146`: rate limiter allows `burst_size=10` (`RateLimitConfig.burst_size` default 10) — exactly the thread pool size, so 10 rapid Scan RPCs from one token occupy all threads.
- Compare `handler_routes_post.py:204-258`: HTTP daemon uses `self.scan_executor` (separate `ThreadPoolExecutor`) and `self.scan_slots` (Semaphore), freeing the HTTP handler thread immediately.
- `auth.py:24-28`: `Health` is NOT in `METHOD_PERMISSIONS` — it bypasses auth. But it still needs a thread from the shared pool, which may not be available when all threads are busy with Scan RPCs.

## Deliverables
1. Run gRPC Scan RPCs on a separate executor (like the HTTP daemon's `scan_executor`), or at minimum decouple the scan thread count from the RPC thread count so Health always has available threads. Option: use a separate small pool for Health/GetPolicy/QueryAudit and the main pool for Scan.
2. Regression test: with `max_workers=2`, submit 2 concurrent Scan RPCs that sleep (mocked), then assert a Health RPC returns within 1s (not blocked by the scans).