# WO8.0.0-104 — Serve: `list_chains` and `chains_summary` O(N) kill_chain per artifact

**Series:** WO8.0.0 (exploration round 2026-08-22)
**Status:** OPEN
**Owner:** (unassigned)
**Priority:** P1 · Effort M · Risk M
**Scope:** `picosentry/serve/services/correlation/engine.py`, `picosentry/serve/api/routers/correlation.py`, `tests/serve/`

**Gate:** `bash scripts/test.sh fast` + test: `GET /chains` with 1000 artifacts returns in <500ms (currently computes kill_chain per artifact).

## Objective
`list_chains` (default `threshold=0`) and `chains_summary` iterate over ALL artifact IDs and call `kill_chain()` for each one. Each `kill_chain` call computes a full timeline (O(events per artifact)). With the engine's max of 5000 artifacts and 1000 events per artifact, a single request can trigger 5000 timeline computations. The `_chains` cache helps on repeat calls, but the first call after any new event ingestion invalidates the cache for that artifact. This makes the correlation API unusably slow at scale.

## Evidence (verified 2026-08-22, explorer; file:line chain)
- `correlation.py:42-51`: when `threshold == 0` (default), calls `all_artifact_ids(org_id=...)` then `kill_chain(artifact_id, org_id=...)` for EACH artifact in a for-loop.
- `engine.py:348-362`: `chains_summary` has the same pattern — iterates `all_artifact_ids` and calls `kill_chain` per artifact.
- `engine.py:126`: every `ingest()` call pops the cached chain for that artifact, so the next `kill_chain` recomputes.
- `engine.py:52`: `_max_artifacts = 5000` — up to 5000 artifacts.
- `engine.py:51`: `_max_events_per_artifact = 1000` — up to 1000 events per artifact.
- `engine.py:201-210`: `critical_chains` also iterates all artifacts and calls `kill_chain` per artifact.

## Deliverables
1. For `list_chains` with `threshold=0`: compute chains in a single pass over the events dict instead of N separate `kill_chain` calls. The per-artifact computation is already O(events), so a single batch pass is O(total_events) vs O(N * events).
2. For `chains_summary`: same batch pass, accumulating stats in one walk.
3. For `critical_chains`: same — compute all chains in one pass, filter by threshold.
4. Regression test per the gate.