"""WO8.0.0-106: _update_threat_score must amortize decay, not iterate all projects per ingest.

The decay loop (for pid in self.threat_scores: *= 0.95) ran on every
ingest — O(N) per ingest, O(N^2) over a batch of N items with N
projects. Now decay only runs once per _decay_interval (60s), so a
batch of 1000 ingests across 500 projects is O(N), not O(N^2).
"""

from __future__ import annotations

import time

from picosentry.serve.services.intelligence import IntelligenceEngine


class TestThreatScoreDecayAmortized:
    def test_decay_runs_once_per_interval(self, monkeypatch):
        engine = IntelligenceEngine.__new__(IntelligenceEngine)
        engine._lock = __import__("threading").Lock()
        engine.patterns = __import__("collections").defaultdict(list)
        engine.threat_scores = __import__("collections").defaultdict(float)
        engine._last_decay_time = time.monotonic()
        engine._decay_interval = 60.0

        # Seed 3 projects with known scores.
        engine.threat_scores["proj-a"] = 10.0
        engine.threat_scores["proj-b"] = 20.0
        engine.threat_scores["proj-c"] = 30.0

        # Ingest into proj-a: decay should NOT run (within interval).
        engine._update_threat_score("proj-a", "high", {"data": {"match_count": 1}})
        assert engine.threat_scores["proj-b"] == 20.0, "decay ran too early"

        # Advance time past the interval, ingest again: decay runs once.
        engine._last_decay_time = time.monotonic() - 61.0
        engine._update_threat_score("proj-a", "high", {"data": {"match_count": 1}})
        assert engine.threat_scores["proj-b"] < 20.0, "decay did not run after interval"
        assert abs(engine.threat_scores["proj-b"] - 19.0) < 0.01, "decay factor wrong"

    def test_ingest_1000_items_500_projects_under_1s(self, caplog):
        import logging

        caplog.set_level(logging.WARNING, logger="picoshogun.Intelligence")
        engine = IntelligenceEngine.__new__(IntelligenceEngine)
        engine._lock = __import__("threading").Lock()
        engine.patterns = __import__("collections").defaultdict(list)
        engine.threat_scores = __import__("collections").defaultdict(float)
        engine._last_decay_time = time.monotonic()
        engine._decay_interval = 60.0

        for i in range(500):
            engine.threat_scores[f"proj-{i:04d}"] = 1.0

        start = time.perf_counter()
        for i in range(1000):
            project = f"proj-{i % 500:04d}"
            engine._update_threat_score(project, "medium", {"data": {"match_count": 1}})
        elapsed = time.perf_counter() - start

        assert elapsed < 1.0, f"1000 ingests / 500 projects took {elapsed:.3f}s (>1s)"

    def test_scores_still_accumulate_between_decays(self):
        engine = IntelligenceEngine.__new__(IntelligenceEngine)
        engine._lock = __import__("threading").Lock()
        engine.patterns = __import__("collections").defaultdict(list)
        engine.threat_scores = __import__("collections").defaultdict(float)
        engine._last_decay_time = time.monotonic()
        engine._decay_interval = 60.0

        engine.threat_scores["proj-a"] = 10.0
        for _ in range(5):
            engine._update_threat_score("proj-a", "high", {"data": {"match_count": 1}})

        # 5 high-severity ingests: 10.0 + 5 * 5.0 = 35.0 (no decay within interval).
        assert engine.threat_scores["proj-a"] == 35.0
