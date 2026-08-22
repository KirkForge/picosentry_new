# WO8.0.0-004 — Scan: PyPI advisory reachability under-reports dotted package names

**Series:** WO8.0.0 (exploration round 2026-08-22)
**Status:** OPEN
**Owner:** (unassigned — worktree `wo/8.0.0/advisory-pypi-reachable-dotted`)
**Priority:** P1 · Effort S · Risk L
**Scope:** `picosentry/scan/rules/advisory_check.py`, `tests/scan/`

**Gate:** `bash scripts/test.sh fast` + test: a project that imports `ruamel.yaml` and has a `ruamel.yaml` advisory produces a Finding with `reachable=True`.

## Objective
The PyPI reachability check normalizes the package name by replacing `-` and `.` with `_`, but the import extractor splits on `.` and takes only the top-level module. So `import ruamel.yaml` yields the import name `"ruamel"`, while the package `"ruamel.yaml"` normalizes to `"ruamel_yaml"`. Since `"ruamel" != "ruamel_yaml"`, the package is marked `reachable=False` even though it IS imported. Advisory findings for dotted PyPI package names (`ruamel.yaml`, `python-dateutil` imported as `dateutil`, etc.) under-report reachability, making triage harder and potentially filtering out real threats if reachability is used for prioritization.

## Evidence (verified 2026-08-22, read-only explorer; live repro in /tmp/opencode)
- `advisory_check.py:413`: `root = mod.split(".", 1)[0].replace("-", "_").replace(" ", "_").lower()` — import extraction takes only the top-level module (`ruamel` from `ruamel.yaml`).
- `advisory_check.py:431-432`: `return pkg_name.replace("-", "_").replace(".", "_").lower() in imports` — package name `ruamel.yaml` normalizes to `ruamel_yaml`.
- Live repro:
  - `import ruamel.yaml` -> extracted import set: `{"ruamel", "flask"}`
  - `"ruamel.yaml"` normalized for check: `"ruamel_yaml"`
  - `"ruamel_yaml" in {"ruamel", "flask"}` -> `False` (WRONG — the package IS imported)
- Note: `python-dateutil` is imported as `dateutil` (top-level module name differs from package name), so the normalization mismatch is even more fundamental for that common package. The check should also try the top-level module name of the package (first segment after `.`/`_` normalization).

## Deliverables
1. In `_package_in_imports` for the pypi ecosystem, also check the first segment of the normalized package name (split on `_`/`.`) against the imports set, so `ruamel.yaml` matches both `ruamel_yaml` AND `ruamel`.
2. Regression test: a project with `import ruamel.yaml` in a source file and a `ruamel.yaml` advisory produces a Finding with `reachable=True`.