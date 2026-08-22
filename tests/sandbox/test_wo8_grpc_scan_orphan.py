"""WO8.0.0-001: gRPC Scan marks job as 'failed' (not orphaned 'running') on scan failure."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from picosentry.sandbox.grpc_transport._servicer import PicoDomeServicer


class _FakeSandboxResult:
    def __init__(self, verdict="ALLOW", exit_code=0):
        self.overall_verdict = type("V", (), {"value": verdict})()
        self.exit_code = exit_code
        self.duration_ms = 1

    def to_dict(self, deterministic=False):
        return {"verdict": self.overall_verdict.value}


class _FakeAnalysisResult:
    def __init__(self, verdict="CLEAN"):
        self.overall_verdict = type("V", (), {"value": verdict})()
        self.findings = []

    def to_dict(self, deterministic=False):
        return {"verdict": self.overall_verdict.value}


class _RecordingStore:
    def __init__(self):
        self.added = []
        self.updates = []

    def add(self, job_id, command, actor, tenant_id=None):
        self.added.append(job_id)
        return {"job_id": job_id, "status": "pending"}

    def update(self, job_id, **kwargs):
        self.updates.append((job_id, dict(kwargs)))


def _make_request():
    request = MagicMock()
    request.command = ["echo", "hello"]
    request.policy = ""
    request.timeout = 30.0
    request.cwd = ""
    return request


def _make_context():
    context = MagicMock()
    context.invocation_metadata.return_value = []
    context.is_active = lambda: True
    return context


def test_scan_failure_marks_job_failed():
    store = _RecordingStore()
    engine = MagicMock()
    engine.scan = MagicMock(side_effect=RuntimeError("scan engine exploded"))
    servicer = PicoDomeServicer(
        scan_engine=engine,
        start_time=time.time(),
        scan_count_ref=MagicMock(),
        job_store=store,
    )

    servicer.Scan(_make_request(), _make_context())

    assert len(store.added) == 1
    job_id = store.added[0]
    failed_updates = [u for u in store.updates if u[0] == job_id and u[1].get("status") == "failed"]
    assert len(failed_updates) == 1, f"expected a 'failed' update for {job_id}, got {store.updates}"
    assert "scan_failed" in failed_updates[0][1]["error"]


def test_scan_analyze_failure_marks_job_failed():
    store = _RecordingStore()
    engine = MagicMock()
    engine.scan = MagicMock(return_value=_FakeSandboxResult())
    engine.analyze = MagicMock(side_effect=RuntimeError("analyze exploded"))
    servicer = PicoDomeServicer(
        scan_engine=engine,
        start_time=time.time(),
        scan_count_ref=MagicMock(),
        job_store=store,
    )

    servicer.Scan(_make_request(), _make_context())

    job_id = store.added[0]
    statuses = [u[1].get("status") for u in store.updates if u[0] == job_id]
    assert "failed" in statuses, f"expected 'failed' in {statuses}"
    assert statuses[-1] == "failed", f"final status must be 'failed', got {statuses}"


def test_scan_success_does_not_mark_failed():
    store = _RecordingStore()
    engine = MagicMock()
    engine.scan = MagicMock(return_value=_FakeSandboxResult())
    engine.analyze = MagicMock(return_value=_FakeAnalysisResult())
    servicer = PicoDomeServicer(
        scan_engine=engine,
        start_time=time.time(),
        scan_count_ref=MagicMock(),
        job_store=store,
    )

    servicer.Scan(_make_request(), _make_context())

    job_id = store.added[0]
    statuses = [u[1].get("status") for u in store.updates if u[0] == job_id]
    assert "completed" in statuses
    assert "failed" not in statuses


def test_scan_failure_without_store_does_not_crash():
    engine = MagicMock()
    engine.scan = MagicMock(side_effect=RuntimeError("boom"))
    servicer = PicoDomeServicer(
        scan_engine=engine,
        start_time=time.time(),
        scan_count_ref=MagicMock(),
        job_store=None,
    )

    result = servicer.Scan(_make_request(), _make_context())
    assert result is not None
