"""L4-ENV-002 false-positive regression — WO8.0.0-006.

Gate: a network call to `redis_url.cache.internal` does NOT produce L4-ENV-002
(benign hostname containing an env var NAME is not exfil). The rule was
removed because checking env var NAMES in addresses is not a real exfil
signal; checking env var VALUES requires a profile schema change that
captures env values (out of scope for this WO).
"""

from __future__ import annotations

from picosentry.sandbox.l4.engine import create_default_engine
from picosentry.sandbox.l4.models import BehavioralProfile, NetworkCall
from picosentry.sandbox.models import Severity


class TestL4Env002FalsePositive:
    def test_benign_hostname_matching_env_var_name_no_critical(self):
        profile = BehavioralProfile(
            package="benign-cache-client",
            network_calls=[NetworkCall(address="redis_url.cache.internal", port=6379)],
            total_runtime_ms=100,
        )
        result = create_default_engine().analyze(profile, deterministic=True)
        critical = [f for f in result.findings if f.severity == Severity.CRITICAL]
        assert critical == [], f"Benign hostname produced CRITICAL: {[(f.rule_id, f.message) for f in critical]}"
        assert not any(f.rule_id == "L4-ENV-002" for f in result.findings)

    def test_benign_mongo_hostname_no_critical(self):
        profile = BehavioralProfile(
            package="benign-db-client",
            network_calls=[NetworkCall(address="mongo_url.svc.cluster.local", port=27017)],
            total_runtime_ms=100,
        )
        result = create_default_engine().analyze(profile, deterministic=True)
        critical = [f for f in result.findings if f.severity == Severity.CRITICAL]
        assert critical == [], f"Benign hostname produced CRITICAL: {[(f.rule_id, f.message) for f in critical]}"
        assert not any(f.rule_id == "L4-ENV-002" for f in result.findings)

    def test_uppercase_env_var_name_in_address_no_finding(self):
        profile = BehavioralProfile(
            package="benign",
            network_calls=[NetworkCall(address="REDIS_URL.host.com", port=443)],
            total_runtime_ms=100,
        )
        result = create_default_engine().analyze(profile, deterministic=True)
        assert not any(f.rule_id == "L4-ENV-002" for f in result.findings)

    def test_l4_env_002_rule_no_longer_registered(self):
        engine = create_default_engine()
        findings = engine.analyze(
            BehavioralProfile(
                package="x",
                network_calls=[NetworkCall(address="redis_url.cache.internal", port=6379)],
                total_runtime_ms=100,
            ),
            deterministic=True,
        ).findings
        assert all(f.rule_id != "L4-ENV-002" for f in findings)
