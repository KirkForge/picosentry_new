# WO9.0.0-104 — CI: push to main/dev has no lint/typecheck job → direct-to-dev pushes skip ruff/mypy

**Series:** WO9.0.0 (audit round 2026-08-23)
**Status:** OPEN
**Owner:** (unassigned)
**Priority:** P1 · Effort S · Risk L
**Scope:** `.github/workflows/ci.yml`

**Gate:** `bash scripts/test.sh fast` + check: a push to `dev` that introduces a ruff/mypy violation fails CI (not just PRs).

## Objective
The `lint` and `type-check` jobs in `ci.yml` are gated to `if: github.event_name == 'pull_request'` (lines 74 and 84). There is NO lint or typecheck job in the push tier. The documented flow (AGENTS.md §1.5) is "routine work commits directly to `dev`", and `dev` is the branch that gets ff'd to `main`. A direct push to `dev` that introduces a ruff or mypy regression passes push CI (which only runs `test-matrix`, `docker-build`, `reproducible-build`, `postgres-live-test`, `landlock-real-exec`, `scan-artifacts-push`) and lands on `dev` with no lint gate. The regression only surfaces if a later PR happens to touch the same area (and even then only in the PR-tier lint, not as a merge blocker). The AGENTS.md contract requires "ruff/format/mypy clean" on every commit, but push CI does not enforce it for the direct-to-dev flow.

## Evidence (verified 2026-08-23, explorer; file:line chain)
- `ci.yml:73-80`: `lint` job — `if: github.event_name == 'pull_request'`; runs `ruff check` and `ruff format --check`.
- `ci.yml:82-89`: `type-check` job — `if: github.event_name == 'pull_request' && needs.changes.outputs.code == 'true'`; runs `mypy picosentry/`.
- Push jobs (no lint/typecheck):
  - `ci.yml:139` `scan-artifacts-push` (push only)
  - `ci.yml:198` `test-matrix` (push only — pytest, no lint)
  - `ci.yml:220` `postgres-live-test` (push only)
  - `ci.yml:280` `reproducible-build` (push only)
  - `ci.yml:326` `docker-build` (push only)
  - `ci.yml:357` `docker-build-arm64` (push only)
  - `ci.yml:382` `landlock-real-exec` (push only)
- AGENTS.md §1.5: "routine work commits directly to `dev`" — the direct-to-dev flow is the primary commit path, and it has no lint/typecheck gate.
- AGENTS.md §4: "Gates for this repo: Lint `uv run ruff check`; Typecheck `uv run mypy picosentry/`" — required on every commit, not enforced on push.

## Deliverables
1. Add a `lint-push` job to `ci.yml` (push tier, `if: github.event_name == 'push'`) running `uv run --extra dev ruff check picosentry/ tests/ scripts/` and `uv run --extra dev ruff format --check picosentry/ tests/ scripts/`.
2. Add a `type-check-push` job to `ci.yml` (push tier, `if: github.event_name == 'push'`) running `uv run --extra dev mypy picosentry/`.
3. (Optional) Combine into the existing `lint`/`type-check` jobs by widening the `if` to `github.event_name == 'pull_request' || github.event_name == 'push'` — same job, runs on both event types.