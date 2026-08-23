# WO9.0.0-105 — Deploy: Dockerfile HEALTHCHECK for `server` target checks imports, not the HTTP endpoint

**Series:** WO9.0.0 (audit round 2026-08-23)
**Status:** OPEN
**Owner:** (unassigned)
**Priority:** P1 · Effort S · Risk L
**Scope:** `Dockerfile`

**Gate:** `bash scripts/test.sh fast` + check: the serve Docker image's `HEALTHCHECK` probes the HTTP `/health` endpoint (or is removed in favor of the helm chart's probes), not `picosentry health` (import-only).

## Objective
The Dockerfile `base` stage (line 61-62) defines `HEALTHCHECK ... CMD picosentry health || exit 1`. This HEALTHCHECK is inherited by every downstream target: `scanner`, `sandbox`, `server`, `all`. The `picosentry health` CLI command (`cli_commands/health.py`) only verifies that `picosentry.scan`, `picosentry.sandbox`, `picosentry.watch`, and `picosentry.serve` modules import successfully — it does NOT start the serve process or probe its HTTP endpoint. For the `server` target (line 100, the serve image), a container where the uvicorn process has crashed or hung but the Python imports still succeed reports "healthy" to Docker's HEALTHCHECK. This produces a false-healthy signal for `docker run` / `docker-compose` users who rely on the image's built-in healthcheck (k8s deployments are unaffected — the serve helm chart uses its own HTTP `/health` liveness/readiness probes at `deployment.yaml:154-177`).

## Evidence (verified 2026-08-23, explorer; file:line chain)
- `Dockerfile:61-62`: `HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \ CMD picosentry health || exit 1` — defined in the `base` stage, inherited by all targets.
- `Dockerfile:100`: `FROM base AS server` — the serve target inherits the import-only HEALTHCHECK.
- `cli_commands/health.py:14-57`: `cmd()` only runs `import picosentry.scan.engine`, `from picosentry.sandbox import __version__`, `from picosentry.watch import __version__`, `from picosentry.serve.config.version import __version__` — pure import checks, no HTTP probe, no process liveness.
- `deploy/helm/serve/templates/deployment.yaml:154-177`: the k8s liveness/readiness probes hit `httpGet path: /health port: http` — correct, HTTP-level. So k8s is fine; only `docker run` / `docker-compose` rely on the Dockerfile HEALTHCHECK.
- Contrast: the `picodome` helm chart and the `scanner`/`sandbox` targets legitimately use `picosentry health` (no HTTP server to probe). Only the `server` target has an HTTP endpoint that the HEALTHCHECK should probe.

## Deliverables
1. Override the HEALTHCHECK in the `server` target (line 100+) to probe the HTTP endpoint: `HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://localhost:${PICOSHOGUN_API_PORT:-8765}/health', timeout=4).read(); sys.exit(0)" || exit 1`. The port comes from `PICOSHOGUN_API_PORT` (default 8765 per `cli_commands/serve.py:20`; the serve helm chart uses 8766 via `serve.port` — confirm the env var is wired in `deployment.yaml:88-91`, it is).
2. (Alternative) Remove the inherited HEALTHCHECK from the `server` target (`HEALTHCHECK NONE`) and rely solely on the helm chart's probes for k8s, accepting that `docker run` users have no built-in healthcheck for the serve image. Option 1 is preferred (keeps `docker run` honest).
3. Regression check per the gate.