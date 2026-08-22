# WO8.0.0-002 — Scan: ScanCache `_enforce_caps` O(n) on every put (same class as WO7-031)

**Series:** WO8.0.0 (exploration round 2026-08-22)
**Status:** OPEN
**Owner:** (unassigned — worktree `wo/8.0.0/scan-cache-enforce-caps`)
**Priority:** P1 · Effort S-M · Risk L
**Scope:** `picosentry/scan/cache.py`, `tests/scan/`

**Gate:** `bash scripts/test.sh fast` + test: `put()` called 1000 times with `max_entries=100` completes in bounded time (no O(n²) growth); `_enforce_caps` runs at most every N writes, not every write.

## Objective
`ScanCache.put()` calls `self._enforce_caps()` unconditionally on every write (line 244). `_enforce_caps()` (lines 121-174) reads and `json.loads()` EVERY `*.json` file in the cache directory on every call. With n cache entries this is O(n) per put, O(n²) for n sequential puts — the exact same bug class as WO7-031 (OSV disk-cache O(N²)), but in the scan result cache. The OSV client fixed this with `_ENFORCE_CAPS_EVERY = 50` (intelligence.py:66) gating; the scan result cache has no such gate.

## Evidence (verified 2026-08-22, read-only explorer; file:line chain)
- `cache.py:244`: `self._enforce_caps()` called unconditionally at end of `put()`.
- `cache.py:126-131`: `_enforce_caps` iterates `self.cache_dir.glob("*.json")` and `json.loads(path.read_text(...))` for EVERY file — O(n) parse per call.
- `cache.py:121-174`: full method body — no write-count gate, no amortization.
- Compare `intelligence.py:64-66`: `OSVClient` has `_ENFORCE_CAPS_EVERY = 50` and `self._write_count` (line 133-135) gating `_enforce_caps` to every 50th write — the WO7-031 fix. `ScanCache` has no equivalent.

## Deliverables
1. Add a `_write_count` counter and `_ENFORCE_CAPS_EVERY` gate to `ScanCache` (same pattern as `OSVClient`), so `_enforce_caps` runs at most every N writes instead of every write.
2. Regression test: write 1000 entries with `max_entries=100`, assert total time is bounded (no O(n²) growth); assert `_enforce_caps` call count is ~N/50, not N.