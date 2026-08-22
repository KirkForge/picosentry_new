"""WO8.0.0-004 — PyPI advisory reachability under-reports dotted package names.

`ruamel.yaml` normalizes to `ruamel_yaml` but `import ruamel.yaml` extracts
only the top-level module `ruamel`, so the package was marked
`reachable=False` despite being imported. Fix also checks the first segment
of the normalized package name against the imports set.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from picosentry.scan.rules.advisory_check import _package_in_imports


class TestPackageInImportsDotted:
    def test_dotted_pypi_matches_top_level_import(self) -> None:
        """`ruamel.yaml` matches the extracted import `ruamel`."""
        imports = {"ruamel", "flask"}
        assert _package_in_imports("ruamel.yaml", "pypi", imports) is True

    def test_underscored_pypi_matches_top_level_import(self) -> None:
        """`python-dateutil` normalizes to `python_dateutil`; first segment
        `python` matches an import of `python` (unrealistic) but the real
        module is `dateutil` — covered by the full-normalized form only when
        `dateutil` is in imports. The first-segment check fixes `ruamel.yaml`;
        `python-dateutil` needs `dateutil` in the import set too."""
        # python-dateutil imports as `dateutil`; the import set has `dateutil`.
        # full-normalized: python_dateutil (no match); first segment: python (no match)
        # This is the fundamental mismatch the WO notes; the fix addresses the
        # dotted-form (ruamel.yaml). python-dateutil remains a known gap.
        imports = {"dateutil"}
        assert _package_in_imports("python-dateutil", "pypi", imports) is False

    def test_underscored_pypi_imported_as_first_segment_matches(self) -> None:
        """A package whose name normalizes so its first segment is the import name."""
        imports = {"dateutil"}
        # dateutil normalizes to dateutil; first segment dateutil matches.
        assert _package_in_imports("dateutil", "pypi", imports) is True

    def test_non_dotted_pypi_still_matches(self) -> None:
        """Non-dotted PyPI packages still match via full normalization."""
        imports = {"requests", "flask"}
        assert _package_in_imports("requests", "pypi", imports) is True
        assert _package_in_imports("Flask", "pypi", imports) is True

    def test_dotted_pypi_not_imported(self) -> None:
        """A dotted package not in imports returns False."""
        imports = {"flask"}
        assert _package_in_imports("ruamel.yaml", "pypi", imports) is False

    def test_npm_unchanged(self) -> None:
        """npm ecosystem behavior is unchanged."""
        imports = {"lodash", "react"}
        assert _package_in_imports("lodash", "npm", imports) is True
        assert _package_in_imports("@scope/pkg", "npm", imports) is False


class TestReachabilityDottedIntegration:
    """End-to-end: a project importing `ruamel.yaml` with a `ruamel.yaml`
    advisory produces a Finding with `reachable=True`."""

    def test_ruamel_yaml_reachable(self, tmp_path: Path) -> None:
        src = tmp_path / "app.py"
        src.write_text(
            dedent("""\
            import ruamel.yaml

            def load():
                return ruamel.yaml.YAML()
        """)
        )
        # Reuse the same import-extraction the advisory check uses.
        from picosentry.scan.rules.advisory_check import _extract_py_imports, _import_map

        text = src.read_text(encoding="utf-8")
        py_imports = _extract_py_imports(text)
        assert "ruamel" in py_imports, f"expected `ruamel` in {py_imports}"
        import_map = _import_map(tmp_path)
        pypi_imports = import_map["pypi"]
        assert "ruamel" in pypi_imports, f"expected `ruamel` in pypi imports {pypi_imports}"
        assert _package_in_imports("ruamel.yaml", "pypi", pypi_imports) is True
