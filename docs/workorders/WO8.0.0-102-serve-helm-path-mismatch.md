# WO8.0.0-102 — Deploy: serve helm chart path mismatch (Dockerfile user vs helm mount path)

**Series:** WO8.0.0 (exploration round 2026-08-22)
**Status:** OPEN
**Owner:** (unassigned)
**Priority:** P0 · Effort S · Risk L
**Scope:** `deploy/helm/serve/values.yaml`, `deploy/helm/serve/templates/deployment.yaml`, `Dockerfile`

**Gate:** `bash scripts/test.sh fast` + `helm template deploy/helm/serve` renders without path/user mismatch warnings.

## Objective
The Dockerfile creates user `picosentry` with home `/home/picosentry` (via `useradd -r`, UID < 1000), but the serve helm chart sets `runAsUser: 1000` and mounts the PVC at `/home/picodome/.picosentry`. The path `/home/picodome/` does not exist in the Docker image — the user's home is `/home/picosentry/`. While the DB path is correctly env-var-overridden to the PVC mount, the mismatch means: (a) any code that reads `~` or `$HOME` gets `/home/picosentry` (the Docker USER's home) not `/home/picodome` (where the PVC is); (b) the `DEFAULT_USER_PLUGIN_DIR = str(Path("~/.picosentry/plugins").expanduser())` in `plugin_manager.py:114` resolves to `/home/picosentry/.picosentry/plugins` which is on the read-only root FS, not the PVC.

## Evidence (verified 2026-08-22, explorer; file:line chain)
- `Dockerfile:43-46`: `useradd -r -g picosentry -d /home/picosentry -s /sbin/nologin picosentry` — system user, home `/home/picosentry`.
- `Dockerfile:75,88,103,118`: `USER picosentry` — process runs as this user.
- `values.yaml:33`: `path: "/home/picodome/.picosentry/picoshogun.db"` — DB path under `/home/picodome/`.
- `deployment.yaml:138`: `mountPath: /home/picodome/.picosentry` — PVC mounted at `/home/picodome/`.
- `values.yaml:124`: `runAsUser: 1000` — overrides the Docker USER to UID 1000 (not the picosentry system user).
- `plugin_manager.py:114`: `DEFAULT_USER_PLUGIN_DIR = str(Path("~/.picosentry/plugins").expanduser())` — resolves to the Docker user's home, not the PVC mount.

## Deliverables
1. Align the PVC mount path and DB path to the Docker image's user home (`/home/picosentry/.picosentry`), OR set `HOME=/home/picodome/.picosentry` in the deployment env so `~` resolves to the PVC.
2. Document that `runAsUser: 1000` overrides the Docker USER and the process does NOT run as the `picosentry` system user — either align the UID or document the override.
3. Regression test per the gate.