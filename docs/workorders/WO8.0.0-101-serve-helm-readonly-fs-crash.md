# WO8.0.0-101 — Deploy: serve helm chart crashes on boot (readOnlyRootFilesystem + hardcoded log/backup dirs)

**Series:** WO8.0.0 (exploration round 2026-08-22)
**Status:** OPEN
**Owner:** (unassigned)
**Priority:** P0 · Effort M · Risk M
**Scope:** `picosentry/serve/config/settings.py`, `picosentry/serve/services/log_manager.py`, `picosentry/serve/config/logging_config.py`, `deploy/helm/serve/templates/deployment.yaml`, `deploy/helm/serve/values.yaml`, `tests/serve/`

**Gate:** `bash scripts/test.sh fast` + test: serve container boots with `readOnlyRootFilesystem: true` and writes logs/backups to the PVC mount, not the root filesystem.

## Objective
The serve helm chart sets `readOnlyRootFilesystem: true` (deployment.yaml:143) but `log_dir` and `backup_dir` are hardcoded to `BASE_DIR / "logs"` and `BASE_DIR / "backups"` (inside the wheel install, which is read-only). The `LogManager.__init__` calls `self.log_dir.mkdir(parents=True, exist_ok=True)` at import time — this raises `PermissionError` on a read-only filesystem and crashes the container before it starts. `BackupManager.create_backup` has the same problem. Neither path has an env var override, and neither points to the PVC mount at `/home/picodome/.picosentry`.

## Evidence (verified 2026-08-22, explorer; file:line chain)
- `settings.py:58`: `backup_dir: Path = BASE_DIR / "backups"` — hardcoded, no env var override.
- `settings.py:182`: `log_dir: Path = BASE_DIR / "logs"` — hardcoded, no env var override.
- `log_manager.py:17`: `self.log_dir = Path(log_dir) if log_dir else Path(__file__).parent.parent / "logs"` — falls back to same hardcoded path.
- `log_manager.py:25`: `self.log_dir.mkdir(parents=True, exist_ok=True)` — crashes on read-only FS.
- `log_manager.py:167`: `log_manager = LogManager()` — module-level singleton, runs at import time.
- `admin.py:22`: `from picosentry.serve.services.log_manager import log_manager` — imported at module level.
- `server.py:40`: `from picosentry.api.routers import (..., admin, ...)` — triggers the import chain.
- `deployment.yaml:143`: `readOnlyRootFilesystem: true` — the root filesystem is read-only.
- `deployment.yaml:138`: `mountPath: /home/picodome/.picosentry` — PVC mount, but log_dir/backup_dir don't point here.
- `values.yaml:33`: `path: "/home/picodome/.picosentry/picoshogun.db"` — DB path is on the PVC, but logs/backups are not.
- Live repro: `mkdir -p /tmp/opencode/ro && chmod 444 /tmp/opencode/ro && python3 -c "import pathlib; pathlib.Path('/tmp/opencode/ro/logs').mkdir(parents=True, exist_ok=True)"` raises `PermissionError`.

## Deliverables
1. Add `PICOSHOGUN_LOG_DIR` env var override for `settings.logging.log_dir` (default: `BASE_DIR / "logs"`).
2. Add `PICOSHOGUN_BACKUP_DIR` env var override for `settings.database.backup_dir` (default: `BASE_DIR / "backups"`).
3. Wire both env vars in the serve helm deployment template to point at the PVC mount (`/home/picodome/.picosentry/logs` and `/home/picodome/.picosentry/backups`).
4. Guard `log_manager.py:25` `mkdir` with a try/except for `OSError` so a read-only FS degrades to console-only logging instead of crashing.
5. Regression test per the gate.