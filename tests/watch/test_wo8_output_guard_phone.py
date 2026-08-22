"""WO8.0.0-007 — output_guard phone PII pattern false-positives on numeric data.

The 2nd alternative of the phone pattern matched any 10-11 digit number,
firing on file sizes (1234567890), durations (123.456.7890), numeric IDs,
and JSON output. Fix requires a `+` country code, parentheses around the
area code, or a `tel:` prefix.
"""

from __future__ import annotations

from pathlib import Path

from picosentry.watch.config import PicoWatchConfig
from picosentry.watch.output_guard import OutputGuard

RULES_DIR = Path(__file__).parent.parent.parent / "picosentry" / "watch" / "rules"


def _make_config(rules_dir: Path, **overrides) -> PicoWatchConfig:
    config = PicoWatchConfig()
    config.rules_dir = rules_dir
    for k, v in overrides.items():
        setattr(config, k, v)
    return config


class TestPhoneFalsePositives:
    """Numeric data must NOT produce `out_pii_phone`."""

    def test_file_size_not_flagged(self) -> None:
        config = _make_config(RULES_DIR)
        guard = OutputGuard(config=config)
        result = guard.validate("File size: 1234567890 bytes")
        assert "out_pii_phone" not in result.violations, (
            f"file size must not be flagged as phone; got {result.violations}"
        )

    def test_duration_not_flagged(self) -> None:
        config = _make_config(RULES_DIR)
        guard = OutputGuard(config=config)
        result = guard.validate("Duration: 123.456.7890 ms")
        assert "out_pii_phone" not in result.violations, (
            f"duration must not be flagged as phone; got {result.violations}"
        )

    def test_numeric_id_not_flagged(self) -> None:
        config = _make_config(RULES_DIR)
        guard = OutputGuard(config=config)
        result = guard.validate("ID: 12345-678901")
        assert "out_pii_phone" not in result.violations

    def test_line_counts_not_flagged(self) -> None:
        config = _make_config(RULES_DIR)
        guard = OutputGuard(config=config)
        result = guard.validate("Scan result: 12345 67890")
        assert "out_pii_phone" not in result.violations

    def test_json_numeric_output_not_flagged(self) -> None:
        config = _make_config(RULES_DIR)
        guard = OutputGuard(config=config)
        result = guard.validate('{"size": 1234567890, "duration_ms": 123.456.7890}')
        assert "out_pii_phone" not in result.violations

    def test_bare_us_format_without_separators_not_flagged(self) -> None:
        """Bare 10-digit numbers without phone structure are not flagged."""
        config = _make_config(RULES_DIR)
        guard = OutputGuard(config=config)
        result = guard.validate("The number is 5551234567 today")
        assert "out_pii_phone" not in result.violations


class TestPhoneTruePositives:
    """Real phone numbers with phone-like structure ARE detected."""

    def test_us_with_country_code_and_parens(self) -> None:
        config = _make_config(RULES_DIR)
        guard = OutputGuard(config=config)
        result = guard.validate("Call +1 (555) 123-4567 now")
        assert "out_pii_phone" in result.violations

    def test_international_with_plus(self) -> None:
        config = _make_config(RULES_DIR)
        guard = OutputGuard(config=config)
        result = guard.validate("Reach us at +44 20 7946 0958")
        assert "out_pii_phone" in result.violations

    def test_us_parens_area_code(self) -> None:
        config = _make_config(RULES_DIR)
        guard = OutputGuard(config=config)
        result = guard.validate("Office: (555) 123-4567")
        assert "out_pii_phone" in result.violations

    def test_tel_prefix(self) -> None:
        config = _make_config(RULES_DIR)
        guard = OutputGuard(config=config)
        result = guard.validate("tel:+15551234567")
        assert "out_pii_phone" in result.violations

    def test_phone_redacted(self) -> None:
        config = _make_config(RULES_DIR)
        guard = OutputGuard(config=config)
        result = guard.validate("Call +1 (555) 123-4567 now")
        assert "out_pii_phone" in result.violations
        assert result.redacted is not None
        assert "[PHONE-REDACTED]" in result.redacted
