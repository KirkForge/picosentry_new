# WO9.0.0-106 — Serve: PluginManager `_load_plugins` iterdir() unguarded → OSError crashes serve import at boot

**Series:** WO9.0.0 (audit round 2026-08-23)
**Status:** OPEN
**Owner:** (unassigned)
**Priority:** P1 · Effort S · Risk L
**Scope:** `picosentry/serve/services/plugin_manager.py`, `tests/serve/`

**Gate:** `bash scripts/test.sh fast` + test: a plugin directory that raises `OSError` during `iterdir()` (permission denied, vanished mid-scan) is logged and skipped, not propagated to crash `PluginManager.__init__`.

## Objective
`PluginManager._load_plugins` (line 345) calls `for plugin_path in d_path.iterdir():` OUTSIDE any try/except. The per-plugin try block (line 366-392) only wraps the manifest read + load, NOT the `iterdir()` call. If `iterdir()` raises `OSError` (permission denied on a subdir, directory deleted between the `is_dir()` check on line 342 and the `iterdir()` call, or a filesystem error), the exception propagates out of `_load_plugins` → `PluginManager.__init__` (line 202) → the module-level singleton `plugin_manager = PluginManager()` (line 589) → the entire `picosentry.serve.services.plugin_manager` import → `picosentry.serve.api.server` import (line 81) → the serve app never starts. A transient filesystem blip on a user-configured `PICOSHOGUN_PLUGIN_DIR` thus takes down the whole serve process at boot with a traceback instead of degrading to "plugins in that dir unavailable".

## Evidence (verified 2026-08-23, explorer; file:line chain)
- `plugin_manager.py:336-339`: `_load_plugins` acquires `self._lock` to snapshot `dirs`, releases it, then iterates.
- `plugin_manager.py:341-342`: `d_path = Path(d); if not d_path.is_dir(): continue` — TOCTOU window between this check and line 345.
- `plugin_manager.py:345`: `for plugin_path in d_path.iterdir():` — NO try/except; `Path.iterdir()` raises `OSError` on permission denied / vanished dir / FS error.
- `plugin_manager.py:366`: `try:` — the per-plugin try block starts AFTER the `iterdir()` call; it cannot catch an `iterdir` failure.
- `plugin_manager.py:202`: `self._load_plugins()` in `__init__`.
- `plugin_manager.py:589`: `plugin_manager = PluginManager()` — module-level singleton, runs at import time. An `OSError` here crashes the import.
- `server.py:81`: `from picosentry.serve.services.plugin_manager import plugin_manager` — import-time failure prevents the serve app from constructing.
- The codebase's own `_PLUGIN_LOAD_ERRORS` tuple (line 27-33) includes `OSError`, confirming OSError is an expected operational failure for plugin loading — but the `iterdir()` site is outside the handler that uses it.

## Deliverables
1. Wrap the `for plugin_path in d_path.iterdir():` loop (line 345) in a try/except for `_PLUGIN_LOAD_ERRORS` (or at least `OSError`): log `logger.warning("Plugin directory %s unreadable: %s", d, exc)` and `continue` to the next directory instead of crashing.
2. Regression test per the gate: monkeypatch `Path.iterdir` to raise `OSError` for one configured dir and assert `_load_plugins` returns (logs the warning) instead of raising.