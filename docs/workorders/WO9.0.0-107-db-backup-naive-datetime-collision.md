# WO9.0.0-107 — Serve: `DatabaseManager.backup()` uses naive `datetime.now()` + same-second filename collision

**Series:** WO9.0.0 (audit round 2026-08-23)
**Status:** OPEN
**Owner:** (unassigned)
**Priority:** P2 · Effort S · Risk L
**Scope:** `picosentry/serve/database/manager.py`, `picosentry/serve/services/backup.py`, `tests/serve/`

**Gate:** `bash scripts/test.sh fast` + test: `db.backup()` filename is UTC-stamped and unique under same-second concurrent calls; `list_backups` returns UTC-consistent timestamps.

## Objective
Two related consistency/correctness issues in the backup path, both contradicting the UTC discipline WO8.0.0-103 (scheduler) and WO8.0.0-109 (log_manager) established:

1. **`DatabaseManager.backup()` (manager.py:385)**: `timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")` — NAIVE local time. The filename `picoshogun_{timestamp}.db` is in local time, while the rest of the codebase uses UTC. Two backups in the same second (concurrent calls, or a rapid manual trigger) produce the same filename and `sqlite3.connect(backup_path)` / the backup write silently overwrites the first. (Note: this method appears to have no production callers today — `BackupManager.create_backup` does its own sqlite backup via `src.backup(dst)` — but it is a public `DatabaseManager` API and the naive-time + collision is a latent bug if ever wired.)

2. **`BackupManager.list_backups()` (backup.py:306)**: `datetime.fromtimestamp(stat.st_ctime).isoformat()` — NAIVE local time in the `created` field, while `create_backup` (backup.py:153) stores `datetime.now(timezone.utc).isoformat()` in metadata. A consumer comparing the list's `created` to the metadata's `created` gets a timezone mismatch.

## Evidence (verified 2026-08-23, explorer; live shell repro)
- `manager.py:385`: `timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")` — naive, no `timezone.utc`.
- `manager.py:386`: `backup_path = backup_dir / f"picoshogun_{timestamp}.db"` — second-granularity; same-second collision.
- `backup.py:125`: `timestamp = datetime.now(timezone.utc).strftime(...)` — `create_backup` correctly uses UTC.
- `backup.py:153`: `datetime.now(timezone.utc).isoformat()` — metadata uses UTC.
- `backup.py:306`: `datetime.fromtimestamp(stat.st_ctime).isoformat()` — naive local time, inconsistent with line 153.
- Live repro (`/tmp/opencode/test_db_backup.py`):
  ```
  db.backup naive: 20260823_032556
  should be UTC:    20260823_012556   # 2h offset (local TZ)
  collision if same second: filename picoshogun_20260823_032556.db
  ```
- Live repro (`/tmp/opencode/test_db_backup_collision.py`): two `datetime.now().strftime(...)` calls in the same second return identical strings (`same=True`).

## Deliverables
1. `manager.py:385`: change `datetime.now()` to `datetime.now(timezone.utc)` for UTC consistency with the rest of the codebase.
2. `manager.py:385-386`: make the filename collision-safe — append a short unique suffix (e.g. `uuid.uuid4().hex[:8]` or an incrementing counter) so concurrent/same-second backups do not overwrite. (Mirrors `BackupManager.create_backup` which already uses `temp_dir = ... / f"temp_{timestamp}_{uuid.uuid4().hex}"` at backup.py:133.)
3. `backup.py:306`: change `datetime.fromtimestamp(stat.st_ctime)` to `datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc)` for UTC consistency with the metadata `created` field.
4. Regression test per the gate.