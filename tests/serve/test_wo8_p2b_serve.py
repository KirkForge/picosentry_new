"""WO8.0.0 P2b serve fixes: 107 (dead acknowledge_alert), 108 (pending_alerts),
109 (log_manager UTC), 110 (find_correlations SQL interval)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from picosentry.serve.database.manager import db
from picosentry.serve.services.intelligence import IntelligenceEngine
from picosentry.serve.services.log_manager import LogManager
from picosentry.serve.services.orchestrator import EnhancedOrchestrator
from tests.serve._integration_helpers import _auth_headers, _register_with_org


# ── WO8.0.0-107: dead acknowledge_alert removed ──────────────────────────


class TestAcknowledgeAlertRemoved:
    """The dead EnhancedOrchestrator.acknowledge_alert method (which set
    sent=1, the WO7-028 bug pattern) must be gone — no method by that name."""

    def test_no_acknowledge_alert_method_on_orchestrator(self):
        assert not hasattr(EnhancedOrchestrator, "acknowledge_alert"), (
            "EnhancedOrchestrator.acknowledge_alert must be removed (dead code, "
            "WO7-028 regression risk: it set sent=1 instead of acknowledged=1)"
        )


# ── WO8.0.0-108: pending_alerts counts acknowledged=0, not sent=0 ────────


class TestPendingAlertsCountsAcknowledged:
    """pending_alerts must reflect unacknowledged alerts, not undelivered
    ones. An alert delivered (sent=1) but not acknowledged (acknowledged=0)
    is the one an operator needs to see as pending."""

    def test_dashboard_pending_counts_unacknowledged_not_undelivered(self, client):
        token, org_id, _slug = _register_with_org(client, role="admin", slug_prefix="pend-ack")

        db.execute_insert(
            "INSERT INTO alerts (project_id, alert_type, severity, message, channel, org_id, sent, acknowledged) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("proj", "test", "high", "delivered not acknowledged", "syslog", org_id, 1, 0),
        )
        db.execute_insert(
            "INSERT INTO alerts (project_id, alert_type, severity, message, channel, org_id, sent, acknowledged) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("proj", "test", "high", "undelivered but acknowledged", "syslog", org_id, 0, 1),
        )

        resp = client.get("/api/v1/dashboard/summary", headers=_auth_headers(token))
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert data["pending_alerts_count"] == 1, (
            f"pending_alerts_count should be 1 (delivered+unacknowledged), got {data['pending_alerts_count']}"
        )

    def test_orchestrator_get_status_pending_counts_acknowledged(self, orchestrator_fresh, monkeypatch):
        org_id = 1
        db.execute_insert(
            "INSERT INTO alerts (project_id, alert_type, severity, message, channel, org_id, sent, acknowledged) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("proj", "test", "high", "acknowledged alert", "syslog", org_id, 1, 1),
        )
        db.execute_insert(
            "INSERT INTO alerts (project_id, alert_type, severity, message, channel, org_id, sent, acknowledged) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("proj", "test", "high", "unacknowledged alert", "syslog", org_id, 1, 0),
        )

        status = orchestrator_fresh.get_status(org_id=org_id)
        assert status["pending_alerts"] == 1, (
            f"pending_alerts should be 1 (unacknowledged), got {status['pending_alerts']}"
        )


@pytest.fixture
def orchestrator_fresh(tmp_path, monkeypatch):
    """A minimal EnhancedOrchestrator for get_status tests."""
    monkeypatch.setenv("PICOSHOGUN_DATABASE_PATH", str(tmp_path / "orch.db"))
    from picosentry.serve.services.orchestrator import EnhancedOrchestrator as _Orch
    from picosentry.serve.services.orchestrator import ProjectMeta

    orch = _Orch()
    orch.registry["test-project"] = ProjectMeta(
        id="test-project",
        name="Test Project",
        category="scan",
        priority=1,
        dependencies=[],
        cron_schedule="",
        estimated_duration=1,
        status="active",
        version="1.0.0",
    )
    return orch


# ── WO8.0.0-109: log_manager uses UTC, not naive local time ─────────────


class TestLogManagerUtc:
    """cleanup() and get_stats() must use timezone-aware UTC datetimes, not
    naive local time, so retention is correct on a TZ-mismatched container."""

    def test_cleanup_cutoff_is_utc(self, tmp_path):
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        manager = LogManager(log_dir=str(log_dir), retention_days=7)

        old_file = log_dir / "old.log.gz"
        old_file.write_bytes(b"old")

        future = datetime.now(timezone.utc) + timedelta(days=10)
        ts = future.timestamp()
        import os

        os.utime(old_file, (ts, ts))
        assert manager.cleanup() == 0, "future-dated file must not be cleaned up"

        past = datetime.now(timezone.utc) - timedelta(days=30)
        ts_past = past.timestamp()
        os.utime(old_file, (ts_past, ts_past))
        assert manager.cleanup() == 1, "past-dated file must be cleaned up"

    def test_get_stats_modified_is_isoformat_utc(self, tmp_path):
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "app.log").write_text("hello\n", encoding="utf-8")
        manager = LogManager(log_dir=str(log_dir))

        stats = manager.get_stats()
        assert stats["file_count"] == 1
        modified = stats["files"][0]["modified"]
        parsed = datetime.fromisoformat(modified)
        assert parsed.tzinfo is not None, f"modified timestamp must be tz-aware, got {modified!r}"


# ── WO8.0.0-110: find_correlations rejects non-int before DB ─────────────


class TestFindCorrelationsInterval:
    """find_correlations must reject a non-integer time_window_hours with
    ValueError before hitting the DB, not emit a malformed SQL string."""

    def test_non_integer_time_window_raises_value_error(self):
        engine = IntelligenceEngine()
        with pytest.raises(ValueError):
            engine.find_correlations(time_window_hours="not-an-int")  # type: ignore[arg-type]

    def test_sql_injection_string_raises_value_error(self):
        engine = IntelligenceEngine()
        with pytest.raises(ValueError):
            engine.find_correlations(time_window_hours="24; DROP TABLE--")  # type: ignore[arg-type]
