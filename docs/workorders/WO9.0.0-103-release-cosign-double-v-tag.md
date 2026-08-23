# WO9.0.0-103 — Deploy: `release.yml` cosign sign targets `:vv<TAG>` (double-v) → Docker image signing fails on every release

**Series:** WO9.0.0 (audit round 2026-08-23)
**Status:** OPEN
**Owner:** (unassigned)
**Priority:** P0 · Effort S · Risk M
**Scope:** `.github/workflows/release.yml`

**Gate:** `bash scripts/test.sh fast` + dry-run check: the cosign sign command in `release.yml` resolves to the same image tag that was pushed (`docker.io/kirkforge/picodome:v<TAG>`, single `v`).

## Objective
The `release.yml` docker job computes `TAG="v${GITHUB_REF_NAME#v}"` (line 125), which strips the leading `v` from the git tag then re-adds it, yielding `TAG=v2.2.0`. The image is built and pushed as `:v2.2.0` (bake uses `${TAG}`, lines 131-142 correct). But the cosign sign step (line 157) uses `cosign sign --yes "docker.io/kirkforge/picodome:v${TAG}"` — prepending a SECOND `v` to a `TAG` that already starts with `v`, producing `docker.io/kirkforge/picodome:vv2.2.0`. That tag does not exist on the registry, so cosign signing fails. Every release that enables `DOCKER_PUSH_ENABLED=true` fails at the signing step (after the image is already published), blocking the release and leaving an unsigned image.

## Evidence (verified 2026-08-23, explorer; live shell repro)
- `release.yml:125`: `TAG="v${GITHUB_REF_NAME#v}"` → for `GITHUB_REF_NAME=v2.2.0`, `TAG=v2.2.0`.
- `release.yml:131`: `TAG="${TAG}" docker buildx bake --push` → image pushed as `:v2.2.0` ✓ (correct).
- `release.yml:132`: `docker buildx imagetools inspect "docker.io/kirkforge/picodome:${TAG}"` → `:v2.2.0` ✓ (correct).
- `release.yml:142`: `docker buildx imagetools inspect "docker.io/kirkforge/picodome:${TAG}"` → `:v2.2.0` ✓ (correct).
- `release.yml:157`: `cosign sign --yes "docker.io/kirkforge/picodome:v${TAG}"` → `:vv2.2.0` ✗ (DOUBLE `v` — tag does not exist).
- `release.yml:162`: `docker run --rm "docker.io/kirkforge/picodome:${TAG}"` → `:v2.2.0` ✓ (correct).
- Live shell repro (`/tmp/opencode/test_release_tag.sh`):
  ```
  GITHUB_REF_NAME="v2.2.0"
  TAG="v${GITHUB_REF_NAME#v}"
  echo "TAG=$TAG"                       # TAG=v2.2.0
  echo "cosign target: ...picodome:v${TAG}"   # ...picodome:vv2.2.0   <-- BUG
  echo "inspect target: ...picodome:${TAG}"  # ...picodome:v2.2.0    <-- correct
  ```
  Only line 157 has the double-`v`; all other `${TAG}` references are correct.

## Deliverables
1. Fix `release.yml:157`: change `cosign sign --yes "docker.io/kirkforge/picodome:v${TAG}"` to `cosign sign --yes "docker.io/kirkforge/picodome:${TAG}"` (remove the spurious `v` prefix — `TAG` already starts with `v`).
2. Regression check: dry-run the shell expansion to confirm all four tag references (`bake`, `inspect` ×2, `cosign`, `docker run`) resolve to the identical `:v<TAG>` string.