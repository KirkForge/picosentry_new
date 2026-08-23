"""WO8.0.0 P2b deploy fixes: 111 (serve monitoring alerts), 112 (duplicate annotations)."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MONITORING_DIR = REPO_ROOT / "deploy" / "monitoring"
PICODOME_ALERTS = MONITORING_DIR / "picodome-alerts.yaml"
SERVE_ALERTS = MONITORING_DIR / "serve-alerts.yaml"


# ── WO8.0.0-111: serve monitoring alert rules exist ──────────────────────


class TestServeAlertsExist:
    """A serve-alerts.yaml must exist with rules for picoshogun_* metrics so
    a serve-side outage is visible to Prometheus alerting."""

    def test_serve_alerts_file_exists(self):
        assert SERVE_ALERTS.is_file(), "deploy/monitoring/serve-alerts.yaml must exist"

    def test_serve_alerts_has_picoshogun_rules(self):
        content = SERVE_ALERTS.read_text()
        assert "picoshogun_api_requests_total" in content, "must alert on API error rate"
        assert "picoshogun_api_request_duration_seconds" in content, "must alert on API latency"
        assert "picoshogun_outbox_poller_alive" in content, "must alert on outbox poller death"
        assert "picoshogun_dropped_audit_records" in content, "must alert on dropped audit records"
        assert "picoshogun_dropped_correlation_events" in content, "must alert on dropped correlation events"
        assert "picoshogun_ws_dropped_messages" in content, "must alert on WS dropped messages"

    def test_serve_alerts_has_alert_names(self):
        content = SERVE_ALERTS.read_text()
        assert "alert: PicoShogunHighErrorRate" in content
        assert "alert: PicoShogunHighLatency" in content
        assert "alert: PicoShogunOutboxPollerDown" in content
        assert "alert: PicoShogunDroppedAuditRecords" in content
        assert "alert: PicoShogunDroppedCorrelationEvents" in content
        assert "alert: PicoShogunWsDroppedMessages" in content

    def test_serve_alerts_is_valid_prometheus_rule(self):
        content = SERVE_ALERTS.read_text()
        assert "apiVersion: monitoring.coreos.com/v1" in content
        assert "kind: PrometheusRule" in content
        assert "groups:" in content
        assert "rules:" in content


# ── WO8.0.0-112: no duplicate annotations in picodome-alerts.yaml ────────


class TestNoDuplicateAnnotations:
    """The PicoDomeWebhookDeliveryFailures alert had two annotations: keys;
    YAML last-wins silently dropped the summary. No alert rule may have
    duplicate mapping keys."""

    def test_no_duplicate_annotations_in_picodome_alerts(self):
        import re

        text = PICODOME_ALERTS.read_text()
        alert_blocks = re.split(r"(?m)^        - alert: ", text)[1:]
        for block in alert_blocks:
            alert_name = block.split("\n", 1)[0].strip()
            annotations_count = len(re.findall(r"^          annotations:", block, re.MULTILINE))
            assert annotations_count <= 1, (
                f"alert '{alert_name}' has {annotations_count} annotations: keys (duplicate keys silently drop values)"
            )

    def test_webhook_failures_has_summary_and_description(self):
        import re

        text = PICODOME_ALERTS.read_text()
        match = re.search(r"alert: PicoDomeWebhookDeliveryFailures.*?(?=\n        - alert:|\Z)", text, re.DOTALL)
        assert match, "PicoDomeWebhookDeliveryFailures alert must exist"
        block = match.group(0)
        assert "summary:" in block, "webhook failures alert must have a summary annotation"
        assert "description:" in block, "webhook failures alert must have a description annotation"
