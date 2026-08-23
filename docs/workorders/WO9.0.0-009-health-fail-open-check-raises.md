# WO9.0.0-009 — Sandbox: HTTP /health defaults to "healthy" when check_health() raises (fail-open health check)

**Series:** WO9.0.0 (audit round 2026-08-23)
**Status:** OPEN
**Owner:** (unassigned)
**Priority:** P2 · Effort S · Risk L
**Scope:** `picosentry/sandbox/daemon/handler_routes_get.py`, `tests/sandbox/`

**Gate:** `bash scripts/test.sh fast` + test: when `check_health()` raises an exception not in its internal `_HEALTH_PROBE_ERRORS` tuple, the HTTP /health endpoint returns 503 (not 200).

## Objective
The HTTP `/health` handler (handler_routes_get.py:188-210) initializes `all_healthy = True`, then calls `check_health()` in a try/except. If `check_health()` succeeds, `all_healthy` is set from the returned checks. But if `check_health()` raises an exception (not caught internally), the `except` at line 196 logs a debug message and leaves `all_healthy = True`. So the health endpoint returns `{"status": "healthy"}` with HTTP 200 — even though the health check crashed.

This is a fail-open health check: a broken daemon (where `check_health()` itself crashes) keeps reporting "healthy" and continues receiving load-balancer traffic. WO7-002 fixed the original bug (hardcoded "healthy" without calling `check_health()`), but this exception path re-introduces the same behavior for the crash case.

The `check_health()` function catches `_HEALTH_PROBE_ERRORS` (OSError, RuntimeError, ValueError, TypeError, ImportError) internally and returns `healthy=False` for each component. But an unexpected exception (e.g. AttributeError, KeyError, RecursionError) would propagate to the handler, which defaults to healthy.

## Evidence (verified 2026-08-23, read-only explorer; file:line chain)
- `handler_routes_get.py:188`: `all_healthy = True` — default.
- `handler_routes_get.py:190-195`: `try: checks = check_health(); all_healthy = all(c.healthy for c in checks)` — sets `all_healthy` from checks on success.
- `handler_routes_get.py:196-197`: `except (OSError, RuntimeError, ValueError, TypeError, ImportError): logger.debug("check_health() failed, defaulting to healthy", exc_info=True)` — leaves `all_healthy = True` on exception.
- `handler_routes_get.py:210`: `self._send_json(health_data, status=200 if all_healthy else 503)` — returns 200 when `all_healthy` is still True from the default.
- `health.py:16-22`: `_HEALTH_PROBE_ERRORS` catches OSError/RuntimeError/ValueError/TypeError/ImportError internally — but NOT AttributeError/KeyError/RecursionError/etc.

## Deliverables
1. Set `all_healthy = False` (not `True`) as the default before the `try` block, OR set `all_healthy = False` in the `except` block. A health check that crashes should report unhealthy, not healthy.
2. Regression test: mock `check_health()` to raise `AttributeError` (not in `_HEALTH_PROBE_ERRORS`), assert `/health` returns 503.