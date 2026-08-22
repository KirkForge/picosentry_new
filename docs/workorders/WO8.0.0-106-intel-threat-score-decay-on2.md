# WO8.0.0-106 — Serve: `_update_threat_score` O(N) decay on every intelligence ingest

**Series:** WO8.0.0 (exploration round 2026-08-22)
**Status:** OPEN
**Owner:** (unassigned)
**Priority:** P1 · Effort S · Risk L
**Scope:** `picosentry/serve/services/intelligence.py`, `tests/serve/`

**Gate:** `bash scripts/test.sh fast` + test: ingesting 1000 intel items with 500 projects completes in <1s (currently O(N) per ingest = O(N^2) total).

## Objective
`_update_threat_score` iterates over ALL projects in `self.threat_scores` and multiplies each by 0.95 on every single intelligence ingest. This is O(N) per ingest where N is the number of projects. With 500 projects and frequent intelligence ingestion (every scan produces intel), this is O(N^2) over a batch. The `threat_scores` dict is loaded from the DB at startup (`_load_historical`) and grows with every new project — it never shrinks.

## Evidence (verified 2026-08-22, explorer; file:line chain)
- `intelligence.py:352-363`: `_update_threat_score` — `for pid in self.threat_scores: self.threat_scores[pid] *= 0.95` iterates ALL projects.
- `intelligence.py:331-350`: `ingest()` calls `_update_threat_score` on every intel item.
- `orchestrator.py:380-381`: `for intel in intel_data: self.intel.ingest(...)` — one run can produce N intel items, each triggering the O(projects) decay.
- `intelligence.py:43-53`: `_load_historical` loads 7 days of intel into `threat_scores` — grows with project count.

## Deliverables
1. Track a global `last_decay_time` and only decay when enough time has passed (e.g. 60s), not on every ingest. Between decays, accumulate raw scores.
2. Alternatively: use an exponential decay formula that doesn't require iterating all keys (e.g. a single global decay factor applied lazily).
3. Regression test per the gate.