"""WO8.0.0-010 — engine computes package_intel over ALL node_modules on every scan.

`scan()` rglob'd every `package.json` (no SKIP_DIRS, including node_modules)
and ran `PackageIntelligence.analyze` per file BEFORE any rule ran — wasted
work when no registered rule accepts `package_intel` in its signature.
Fix gates the whole block on whether any selected rule needs it, and filters
SKIP_DIRS (node_modules/.venv/.git) in the rglob.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from picosentry.scan.engine import ScanEngine
from picosentry.scan.package_intel import PackageIntelligence


def _make_node_modules_project(tmp_path: Path, n_packages: int = 100) -> Path:
    """Build a project with n_packages node_modules entries, each with a package.json."""
    (tmp_path / "package.json").write_text(json.dumps({"name": "root", "version": "1.0.0"}))
    nm = tmp_path / "node_modules"
    nm.mkdir()
    for i in range(n_packages):
        pkg_dir = nm / f"dep-{i}"
        pkg_dir.mkdir()
        (pkg_dir / "package.json").write_text(json.dumps({"name": f"dep-{i}", "version": f"{i}.0.0"}))
    return tmp_path


class TestPackageIntelLazy:
    def test_analyze_not_called_when_no_rule_uses_package_intel(self, tmp_path: Path) -> None:
        """When no selected rule accepts `package_intel` in its signature,
        PackageIntelligence.analyze must NOT be called on any package.json."""
        project = _make_node_modules_project(tmp_path, n_packages=50)
        engine = ScanEngine()
        # Register a single rule that does NOT accept package_intel.
        engine.register("L2-FAKE-001", lambda target: [])
        with patch.object(PackageIntelligence, "analyze", return_value=None) as mock_analyze:
            result = engine.scan(str(project), rules=["L2-FAKE-001"])
        assert mock_analyze.call_count == 0, (
            f"expected 0 PackageIntelligence.analyze calls (no rule uses package_intel), got {mock_analyze.call_count}"
        )
        assert isinstance(result.findings, list)

    def test_skip_dirs_filter_excludes_node_modules(self, tmp_path: Path) -> None:
        """The rglob SKIP_DIRS filter excludes node_modules/ package.json files
        from package_intel computation."""
        project = _make_node_modules_project(tmp_path, n_packages=30)
        engine = ScanEngine()

        # Register a rule that DOES accept package_intel so the loop runs.
        def _rule_needing_intel(target, package_intel=None):
            return []

        engine.register("L2-INTEL-TEST", _rule_needing_intel)
        with patch.object(PackageIntelligence, "analyze", return_value=None) as mock_analyze:
            engine.scan(str(project), rules=["L2-INTEL-TEST"])
        # analyze is called once per non-SKIP_DIRS package.json. node_modules/
        # is in SKIP_DIRS, so only the root package.json should be analyzed.
        analyzed_names = [call.args[0].get("name") for call in mock_analyze.call_args_list if call.args]
        assert "root" in analyzed_names, f"expected root package.json analyzed, got {analyzed_names}"
        assert all(not name.startswith("dep-") for name in analyzed_names), (
            f"node_modules deps must be skipped by SKIP_DIRS; got {analyzed_names}"
        )

    def test_no_intel_computation_for_pure_pypi_project(self, tmp_path: Path) -> None:
        """A pypi project (no package.json) triggers no package_intel work."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "py"\nversion = "1.0"\n')
        engine = ScanEngine()
        engine.register("L2-FAKE-002", lambda target: [])
        with patch.object(PackageIntelligence, "analyze", return_value=None) as mock_analyze:
            engine.scan(str(tmp_path), rules=["L2-FAKE-002"])
        assert mock_analyze.call_count == 0
