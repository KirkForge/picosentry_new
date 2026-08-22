"""WO8.0.0-003 — firewall pypi-to-npm dep parser PEP 508 bug.

The split-chain parser (`req.split(">")[0].split("<")[0]...`) corrupted URL
specs (`package @ http://...` → `package @ http://...`) and `~=` operators
(`package~=1.0` → `package~`). Fix uses `packaging.Requirement` like the
WO7-007 advisory_check fix.
"""

from __future__ import annotations

from picosentry.firewall.scanner import _pep508_dep_name, _pypi_to_npm_manifest


class TestPep508DepName:
    def test_url_spec_extracts_bare_name(self) -> None:
        assert _pep508_dep_name("package @ http://example.com/pkg.tar.gz") == "package"

    def test_tilde_release_extracts_bare_name(self) -> None:
        assert _pep508_dep_name("package~=1.0") == "package"

    def test_extras_extracts_bare_name(self) -> None:
        assert _pep508_dep_name("package[extra]>=1.0") == "package"

    def test_marker_extracts_bare_name(self) -> None:
        assert _pep508_dep_name("package; sys_platform == 'linux'") == "package"

    def test_plain_version(self) -> None:
        assert _pep508_dep_name("requests>=2.20") == "requests"

    def test_exact_match(self) -> None:
        assert _pep508_dep_name("flask===2.0.1") == "flask"

    def test_fallback_for_unparseable(self) -> None:
        # Garbage that packaging can't parse falls back to the split-chain,
        # which strips operator chars (! < > = ;). The fallback returns the
        # leading name segment — same behavior as advisory_check's fallback.
        assert _pep508_dep_name("not-a-valid-spec!!!") == "not-a-valid-spec"


class TestPypiToNpmManifestPep508:
    def test_url_spec_in_requires_dist(self) -> None:
        info = {
            "name": "pkg",
            "version": "1.0",
            "requires_dist": ["package @ http://example.com/pkg.tar.gz"],
        }
        m = _pypi_to_npm_manifest("pkg", "1.0", info)
        assert m is not None
        assert "package" in m["dependencies"]
        assert m["dependencies"]["package"] == "*"
        assert "http" not in " ".join(m["dependencies"].keys())

    def test_tilde_release_in_requires_dist(self) -> None:
        info = {"name": "pkg", "version": "1.0", "requires_dist": ["package~=1.0"]}
        m = _pypi_to_npm_manifest("pkg", "1.0", info)
        assert m is not None
        assert "package" in m["dependencies"]
        assert "~" not in " ".join(m["dependencies"].keys())

    def test_extras_in_requires_dist(self) -> None:
        info = {"name": "pkg", "version": "1.0", "requires_dist": ["package[extra]>=1.0"]}
        m = _pypi_to_npm_manifest("pkg", "1.0", info)
        assert m is not None
        assert "package" in m["dependencies"]
        assert "[" not in " ".join(m["dependencies"].keys())

    def test_marker_in_requires_dist(self) -> None:
        info = {"name": "pkg", "version": "1.0", "requires_dist": ["package; sys_platform == 'linux'"]}
        m = _pypi_to_npm_manifest("pkg", "1.0", info)
        assert m is not None
        assert "package" in m["dependencies"]

    def test_mixed_specs_all_parse(self) -> None:
        info = {
            "name": "pkg",
            "version": "1.0",
            "requires_dist": [
                "requests>=2.20",
                "package @ http://example.com/pkg.tar.gz",
                "package~=1.0",
                "flask[extra]>=1.0",
                "werkzeug; python_version >= '3.8'",
            ],
        }
        m = _pypi_to_npm_manifest("pkg", "1.0", info)
        assert m is not None
        deps = set(m["dependencies"].keys())
        assert deps == {"requests", "package", "flask", "werkzeug"}
