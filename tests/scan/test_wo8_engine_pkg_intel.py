"""WO8.0.0-010 — engine computes package_intel over ALL node_modules on every scan.

`scan()` rglob'd every `package.json` (no SKIP_DIRS, including node_modules)
and ran `PackageIntelligence.analyze` per file BEFORE any rule ran — wasted
work for projects with 1000+ vendored npm deps. Fix adds the SKIP_DIRS filter
(node_modules/.venv/.git) to the rglob, so vendored deps are skipped. The
advisory collector already walks node_modules via iter_node_modules, so
this duplicated that work.

Computation stays unconditional because ScanResult.package_intel is part of
the result contract (test_package_intel_wiring); the SKIP_DIRS filter
removes the O(vendored deps) cost without breaking that contract.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from picosentry.scan.engine import ScanEngine
from picosentry.scan.package_intel import PackageIntelligence


def _make_node_modules_project(tmp_path: Path, n_packages: int = 100) -> Path:
    """Build a project with n_packages node_modules entries + a root package.json."""
    (tmp_path / "package.json").write_text(json.dumps({"name": "root", "version": "1.0.0"}))
    nm = tmp_path / "node_modules"
    nm.mkdir()
    for i in range(n_packages):
        pkg_dir = nm / f"dep-{i}"
        pkg_dir.mkdir()
        (pkg_dir / "package.json").write_text(json.dumps({"name": f"dep-{i}", "version": f"{i}.0.0"}))
    return tmp_path


class TestPackageIntelSkipDirs:
    def test_node_modules_packages_not_analyzed(self, tmp_path: Path) -> None:
        """The SKIP_DIRS filter excludes node_modules/*/package.json from
        package_intel computation — the O(vendored deps) cost is removed."""
        project = _make_node_modules_project(tmp_path, n_packages=100)
        engine = ScanEngine()
        engine.register("L2-FAKE-001", lambda target: [])
        with patch.object(PackageIntelligence, "analyze", return_value=None) as mock_analyze:
            engine.scan(str(project), rules=["L2-FAKE-001"])
        analyzed_names = [call.args[0].get("name") for call in mock_analyze.call_args_list if call.args]
        # Root package.json (not in a SKIP_DIR) IS analyzed (ScanResult contract).
        assert "root" in analyzed_names, f"expected root package.json analyzed, got {analyzed_names}"
        # node_modules deps MUST be skipped by SKIP_DIRS — the perf win.
        node_mod_analyzed = [n for n in analyzed_names if n.startswith("dep-")]
        assert node_mod_analyzed == [], (
            f"node_modules deps must be skipped by SKIP_DIRS; "
            f"got {len(node_mod_analyzed)} analyzed: {node_mod_analyzed[:5]}"
        )

    def test_venv_packages_not_analyzed(self, tmp_path: Path) -> None:
        """A .venv dir with package.json files is skipped too."""
        (tmp_path / "package.json").write_text(json.dumps({"name": "root", "version": "1.0.0"}))
        venv = tmp_path / ".venv" / "lib" / "site-packages" / "pkg"
        venv.mkdir(parents=True)
        (venv / "package.json").write_text(json.dumps({"name": "venv-pkg", "version": "1.0.0"}))
        engine = ScanEngine()
        engine.register("L2-FAKE-002", lambda target: [])
        with patch.object(PackageIntelligence, "analyze", return_value=None) as mock_analyze:
            engine.scan(str(tmp_path), rules=["L2-FAKE-002"])
        analyzed_names = [call.args[0].get("name") for call in mock_analyze.call_args_list if call.args]
        assert "root" in analyzed_names
        assert "venv-pkg" not in analyzed_names, f".venv pkg must be skipped; got {analyzed_names}"

    def test_no_intel_computation_for_pure_pypi_project(self, tmp_path: Path) -> None:
        """A pypi project (no package.json) triggers no package_intel work."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "py"\nversion = "1.0"\n')
        engine = ScanEngine()
        engine.register("L2-FAKE-003", lambda target: [])
        with patch.object(PackageIntelligence, "analyze", return_value=None) as mock_analyze:
            engine.scan(str(tmp_path), rules=["L2-FAKE-003"])
        assert mock_analyze.call_count == 0

    def test_root_package_intel_in_scan_result(self, tmp_path: Path) -> None:
        """ScanResult.package_intel is populated for the root package (contract)."""
        project = _make_node_modules_project(tmp_path, n_packages=10)
        engine = ScanEngine()
        engine.register("L2-FAKE-004", lambda target: [])
        result = engine.scan(str(project), rules=["L2-FAKE-004"])
        assert "root" in result.package_intel, (
            f"expected root in package_intel (ScanResult contract); got {list(result.package_intel.keys())}"
        )
        # node_modules deps must NOT be in package_intel (SKIP_DIRS filter).
        assert all(not k.startswith("dep-") for k in result.package_intel), (
            f"node_modules deps must be skipped; got {list(result.package_intel.keys())}"
        )
