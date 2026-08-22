"""WO8.0.0-005 — CorpusGovernance false-positive reports not loaded from disk on restart.

`_load_state` loaded sources+release_notes but not `_fp_reports`. After a
restart (new instance, same governance_dir), `list_false_positives()` returned
`[]` and `triage_false_positive()` returned `False` even though the report
files existed on disk. Fix loads FP reports from `_fp_dir()/*.json`.
"""

from __future__ import annotations

from pathlib import Path

from picosentry.scan.corpus_governance import CorpusGovernance, FalsePositiveReport


class TestFalsePositiveLoadOnRestart:
    def test_fp_reports_loaded_after_restart(self, tmp_path: Path) -> None:
        gov_dir = tmp_path / "gov"
        gov1 = CorpusGovernance(governance_dir=gov_dir)
        report = FalsePositiveReport(
            finding_id="L2-FORK-001:lodash",
            rule_id="L2-FORK-001",
            package="lodash",
            justification="Legitimate fork",
        )
        gov1.report_false_positive(report)

        # Simulate restart: new instance, same governance_dir.
        gov2 = CorpusGovernance(governance_dir=gov_dir)
        loaded = gov2.list_false_positives()
        assert len(loaded) == 1, f"expected 1 FP loaded from disk after restart, got {len(loaded)}"
        assert loaded[0].finding_id == "L2-FORK-001:lodash"
        assert loaded[0].package == "lodash"

    def test_fp_triage_works_after_restart(self, tmp_path: Path) -> None:
        gov_dir = tmp_path / "gov"
        gov1 = CorpusGovernance(governance_dir=gov_dir)
        report = FalsePositiveReport(
            finding_id="L2-TYPO-001:lodahs",
            rule_id="L2-TYPO-001",
            package="lodahs",
            justification="Not a typo, different package",
        )
        gov1.report_false_positive(report)

        gov2 = CorpusGovernance(governance_dir=gov_dir)
        assert len(gov2.list_false_positives()) == 1
        result = gov2.triage_false_positive(
            finding_id="L2-TYPO-001:lodahs",
            triager="bob",
            status="accepted",
            resolution="suppress",
        )
        assert result is True, "triage must succeed after restart when the FP file exists on disk"
        triaged = gov2.list_false_positives(status="accepted")
        assert len(triaged) == 1
        assert triaged[0].triaged_by == "bob"

    def test_multiple_fp_reports_loaded_after_restart(self, tmp_path: Path) -> None:
        gov_dir = tmp_path / "gov"
        gov1 = CorpusGovernance(governance_dir=gov_dir)
        for i in range(3):
            gov1.report_false_positive(
                FalsePositiveReport(
                    finding_id=f"rule-{i}:pkg-{i}",
                    rule_id=f"rule-{i}",
                    package=f"pkg-{i}",
                )
            )
        assert len(gov1.list_false_positives()) == 3

        gov2 = CorpusGovernance(governance_dir=gov_dir)
        assert len(gov2.list_false_positives()) == 3

    def test_empty_fp_dir_no_error(self, tmp_path: Path) -> None:
        """A fresh governance dir (no FP files) loads empty."""
        gov = CorpusGovernance(governance_dir=tmp_path / "fresh_gov")
        assert gov.list_false_positives() == []

    def test_corrupt_fp_file_skipped(self, tmp_path: Path) -> None:
        """A corrupt FP json file is skipped, not fatal."""
        gov_dir = tmp_path / "gov"
        gov = CorpusGovernance(governance_dir=gov_dir)
        gov.report_false_positive(
            FalsePositiveReport(
                finding_id="good:pkg",
                rule_id="good",
                package="pkg",
            )
        )
        # Write a corrupt file alongside the good one.
        fp_dir = gov_dir / "false_positives"
        (fp_dir / "corrupt.json").write_text("{not valid json", encoding="utf-8")

        gov2 = CorpusGovernance(governance_dir=gov_dir)
        loaded = gov2.list_false_positives()
        assert len(loaded) == 1
        assert loaded[0].finding_id == "good:pkg"
