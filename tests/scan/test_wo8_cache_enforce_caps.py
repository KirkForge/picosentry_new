"""WO8.0.0-002 — ScanCache `_enforce_caps` O(n) on every put.

Same bug class as WO7-031 (OSV disk-cache O(N²)): `_enforce_caps` read and
`json.loads`-ed every `*.json` file in the cache dir on every `put()`. Fix
gates it to every N writes via `_write_count` + `_ENFORCE_CAPS_EVERY`.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from picosentry.scan.audit import configure_audit_sink, reset_audit_sink
from picosentry.scan.cache import ScanCache


class TestEnforceCapsGated(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile

        self.tmpdir = tempfile.mkdtemp()
        configure_audit_sink(path=Path(self.tmpdir) / "audit.jsonl", retention_days=0)

    def tearDown(self) -> None:
        reset_audit_sink()

    def test_enforce_caps_not_called_every_write(self) -> None:
        """`_enforce_caps` runs at most every N writes, not every write."""
        cache = ScanCache(cache_dir=Path(self.tmpdir), ttl=999999, max_entries=100)
        with patch.object(ScanCache, "_enforce_caps", autospec=True) as mock_caps:
            for i in range(100):
                cache.put(f"lock-{i}", f"corpus-{i}", "v1", {"idx": i})
        call_count = mock_caps.call_count
        # With _ENFORCE_CAPS_EVERY=50, 100 writes → at most 2 calls (every 50th).
        assert call_count <= 100 // cache._ENFORCE_CAPS_EVERY + 1, (
            f"expected _enforce_caps gated to ~every {cache._ENFORCE_CAPS_EVERY} writes, "
            f"got {call_count} calls in 100 writes"
        )
        assert call_count < 100, "should not call _enforce_caps on every write (O(N²) bug)"

    def test_write_count_increments(self) -> None:
        cache = ScanCache(cache_dir=Path(self.tmpdir), ttl=999999, max_entries=10)
        assert cache._write_count == 0
        cache.put("a", "b", "v1", {"x": 1})
        assert cache._write_count == 1
        cache.put("c", "d", "v1", {"x": 2})
        assert cache._write_count == 2

    def test_bounded_time_for_many_puts(self) -> None:
        """1000 puts with max_entries=100 triggers ~20 enforce_caps calls, not 1000.

        Wall-clock is environment-dependent (AGENTS.md §3), so the O(n²)→O(n)
        proof is the _enforce_caps CALL COUNT, not elapsed time: 1000 writes
        gated to every 50th → ~20 calls, vs 1000 calls pre-fix.
        """
        cache = ScanCache(cache_dir=Path(self.tmpdir), ttl=999999, max_entries=100)
        with patch.object(ScanCache, "_enforce_caps", autospec=True) as mock_caps:
            for i in range(1000):
                cache.put(f"lock-{i}", f"corpus-{i}", "v1", {"idx": i})
        call_count = mock_caps.call_count
        expected_max = 1000 // cache._ENFORCE_CAPS_EVERY + 1
        assert call_count <= expected_max, (
            f"expected at most {expected_max} _enforce_caps calls for 1000 writes, got {call_count} "
            "(O(n²) would be 1000 calls)"
        )
        assert call_count < 1000, "gate did not reduce _enforce_caps calls below 1-per-write"


if __name__ == "__main__":
    unittest.main()
