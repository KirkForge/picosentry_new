# WO8.0.0-005 — Scan: CorpusGovernance false-positive reports not loaded from disk on restart

**Series:** WO8.0.0 (exploration round 2026-08-22)
**Status:** OPEN
**Owner:** (unassigned — worktree `wo/8.0.0/corpus-governance-fp-load`)
**Priority:** P1 · Effort S · Risk L
**Scope:** `picosentry/scan/corpus_governance.py`, `tests/scan/`

**Gate:** `bash scripts/test.sh fast` + test: after creating a CorpusGovernance instance, reporting a false positive, creating a NEW instance (simulating restart) with the same governance_dir, `list_false_positives()` returns the previously-reported report, and `triage_false_positive()` succeeds.

## Objective
`CorpusGovernance._load_state()` (lines 272-291) loads `sources` and `release_notes` from the governance state file, but does NOT load `_fp_reports` (false-positive reports). `report_false_positive()` (lines 344-362) writes to both the in-memory `_fp_reports` dict and to `_fp_dir()/*.json` files on disk, but `list_false_positives()` (lines 389-393) and `triage_false_positive()` (lines 364-387) only read from the in-memory dict. After a process restart, all previously-reported false positives are invisible — `list_false_positives()` returns `[]` and `triage_false_positive()` returns `False` even though the report files exist on disk.

## Evidence (verified 2026-08-22, read-only explorer; file:line chain)
- `corpus_governance.py:272-291`: `_load_state` loads `sources` (line 283-288) and `release_notes` (line 290-291), but has NO code to load `_fp_reports`.
- `corpus_governance.py:344-362`: `report_false_positive` writes to `self._fp_reports[report_id]` (line 348) AND to `self._fp_dir() / f"{report_id}.json"` (line 350-351) — the on-disk files exist after restart but are never read back.
- `corpus_governance.py:389-393`: `list_false_positives` reads from `self._fp_reports` (in-memory only).
- `corpus_governance.py:364-387`: `triage_false_positive` iterates `self._fp_reports` (in-memory only).
- Result: after restart, `_fp_reports` is `{}` (empty dict from `__init__` line 260), so both methods see zero reports.

## Deliverables
1. In `_load_state` (or `__init__` after `_load_state`), load `_fp_reports` from `_fp_dir()/*.json` files — same pattern as `report_false_positive` writes them.
2. Regression test: report a false positive, create a new `CorpusGovernance` with the same `governance_dir`, assert `list_false_positives()` returns the report and `triage_false_positive()` succeeds.