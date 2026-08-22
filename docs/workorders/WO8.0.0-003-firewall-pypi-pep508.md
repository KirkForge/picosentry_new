# WO8.0.0-003 — Firewall: pypi-to-npm dep parser has same PEP 508 bug as WO7-007

**Series:** WO8.0.0 (exploration round 2026-08-22)
**Status:** OPEN
**Owner:** (unassigned — worktree `wo/8.0.0/firewall-pypi-pep508`)
**Priority:** P1 · Effort S · Risk L
**Scope:** `picosentry/firewall/scanner.py`, `tests/firewall/`

**Gate:** `bash scripts/test.sh fast` + test: `requires_dist` entries with URL specs (`package @ http://...`), `~=` operators, and extras (`package[extra]>=1.0`) all parse to the correct bare package name in the generated npm manifest.

## Objective
The firewall's `_pypi_to_npm_manifest` mapper uses a hand-rolled split-chain PEP 508 parser that has the exact same bugs WO7-007 fixed in the advisory collector. URL specs (`package @ http://...`) produce `"package @ http://..."` as the dependency name; `~=` operators produce `"package~"` (tilde not stripped). The advisory collector was fixed by switching to `packaging.requirements.Requirement` (advisory_check.py:43-57), but the firewall mapper still uses the broken parser, producing corrupted dependency names in the synthesized npm manifest that mislead the L2-DEPC and L2-TYPO rules.

## Evidence (verified 2026-08-22, read-only explorer; live repro in /tmp/opencode)
- `scanner.py:170-173`: `dep_name = _sanitize_pypi_name(req.split(">")[0].split("<")[0].split("=")[0].split("!")[0].split(";")[0].strip())` — the same split-chain parser, does NOT handle `@` (URL specs) or `~` (compatible release).
- `advisory_check.py:43-57`: the WO7-007 fix uses `packaging.requirements.Requirement(dep).name` which correctly handles all forms. The firewall mapper does not.
- Live repro output:
  - `"package @ http://example.com/pkg.tar.gz"` -> `"package @ http://example.com/pkg.tar.gz"` (WRONG, should be `"package"`)
  - `"package~=1.0"` -> `"package~"` (WRONG, should be `"package"`)
  - `"package[extra]>=1.0"` -> `"package"` (correct, `[` split catches it)
  - `"package; sys_platform == 'linux'"` -> `"package"` (correct, `;` split catches it)

## Deliverables
1. Replace the split-chain parser in `_pypi_to_npm_manifest` with `packaging.requirements.Requirement(req).name` (same fix as WO7-007), with the same fallback to the split-chain for unparseable specs.
2. Regression test: feed `requires_dist` entries with URL specs, `~=` operators, extras, and markers; assert the generated npm manifest `dependencies` keys are bare package names.