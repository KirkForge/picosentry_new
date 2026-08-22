# WO8.0.0-010 — Scan: engine computes package_intel over ALL node_modules on every scan (O(n) wasted work)

**Series:** WO8.0.0 (exploration round 2026-08-22)
**Status:** OPEN
**Owner:** (unassigned — worktree `wo/8.0.0/engine-package-intel-perf`)
**Priority:** P1 · Effort S · Risk L
**Scope:** `picosentry/scan/engine.py`, `tests/scan/`

**Gate:** `bash scripts/test.sh fast` + test: a scan with 1000 `node_modules/*/package.json` files does NOT call `PackageIntelligence.analyze` or `fetch_registry_intel` when no registered rule accepts `package_intel` in its signature.

## Objective
`ScanEngine.scan()` (engine.py:454-474) computes `package_intel` for EVERY `package.json` found via `target_path.rglob("package.json")` BEFORE any rule runs. This walks the entire tree including `node_modules/`, reading and `json.loads()`-ing every `package.json`. For a project with 1000+ npm dependencies, this adds seconds of overhead before any rule starts. In connected mode, it also triggers N network fetches (`fetch_registry_intel`) before rules run. The work is wasted when no registered rule accepts `package_intel` in its signature (only rules with `"package_intel" in params` use it, per `_invoke_rule` line 496-498). The `rglob` does not filter `node_modules/` via `SKIP_DIRS`, so vendored dependencies are included.

## Evidence (verified 2026-08-22, read-only explorer; file:line chain)
- `engine.py:457`: `for _pkg_json_path in sorted(target_path.rglob("package.json")):` — no `SKIP_DIRS` filter, walks `node_modules/` too.
- `engine.py:459-470`: reads, `json.loads`, calls `_pkg_intel_analyzer.analyze()` per file; in connected mode, `fetch_registry_intel` per package (network I/O).
- `engine.py:454`: `package_intel: dict[str, PackageIntel] = {}` computed unconditionally, even when no rule needs it.
- `engine.py:496-498`: `if "package_intel" in params and package_intel is not None:` — only rules declaring `package_intel` in their signature use it. Most rules don't.
- Compare `advisory_check.py`: the advisory collector reads `node_modules` separately via `iter_node_modules()`, so the engine's pre-computation duplicates that work.

## Deliverables
1. Make `package_intel` computation lazy: only compute it when a rule's signature includes `package_intel`, or skip `node_modules/` (the advisory collector already covers it).
2. Regression test: with 100 `node_modules/*/package.json` files, assert that a scan with rules that don't accept `package_intel` does not call `PackageIntelligence.analyze`.