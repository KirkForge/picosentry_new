"""WO8.0.0-008: gRPC Scan RPCs don't starve Health (scan_slots reserve)."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

from picosentry.sandbox.grpc_transport._servicer import PicoDomeServicer
import contextlib


class _FakeSandboxResult:
    overall_verdict = type("V", (), {"value": "ALLOW"})()
    exit_code = 0
    duration_ms = 1

    def to_dict(self, deterministic=False):
        return {"verdict": "ALLOW"}


class _FakeAnalysisResult:
    overall_verdict = type("V", (), {"value": "CLEAN"})()

    def __init__(self):
        self.findings = []

    def to_dict(self, deterministic=False):
        return {"verdict": "CLEAN"}


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


def test_health_returns_while_scans_busy():
    """With scan_slots=1 (max_workers=2 reserve=1), 2 concurrent slow scans
    don't block Health: the 2nd scan is rejected early (slot unavailable),
    leaving a thread for Health."""
    scan_slots = threading.Semaphore(1)

    scan_started = threading.Event()
    scan_release = threading.Event()

    def slow_scan(**kw):
        scan_started.set()
        scan_release.wait(timeout=5)
        return _FakeSandboxResult()

    engine = MagicMock()
    engine.scan = slow_scan
    engine.analyze = MagicMock(return_value=_FakeAnalysisResult())

    servicer = PicoDomeServicer(
        scan_engine=engine,
        start_time=time.time(),
        scan_count_ref=MagicMock(),
        scan_slots=scan_slots,
    )

    errors = []
    scan1_started = threading.Event()

    def do_scan1():
        try:
            servicer.Scan(_make_request(), _make_context())
            scan1_started.set()
        except Exception as e:
            errors.append(e)

    t1 = threading.Thread(target=do_scan1)
    t1.start()

    scan_started.wait(timeout=2)
    assert scan_started.is_set(), "scan1 should have started"

    health_result = {"healthy": None}

    def do_health():
        health_result["healthy"] = servicer.Health(MagicMock(), MagicMock())

    # Health should return immediately — scan1 holds the slot but the RPC
    # thread is free (the 2nd scan would be rejected, not Health).
    t_health = threading.Thread(target=do_health)
    t_health.start()
    t_health.join(timeout=1)
    assert not t_health.is_alive(), "Health RPC blocked >1s — scan starved Health"
    assert health_result["healthy"] is not None

    scan_release.set()
    t1.join(timeout=2)


def test_scan_rejected_when_slots_exhausted():
    """When all scan_slots are taken, a Scan RPC is rejected early (not blocked)."""
    scan_slots = threading.Semaphore(1)
    scan_slots.acquire()

    engine = MagicMock()
    engine.scan = MagicMock(return_value=_FakeSandboxResult())
    engine.analyze = MagicMock(return_value=_FakeAnalysisResult())

    store_updates = []

    class _Store:
        def add(self, job_id, command, actor, tenant_id=None):
            return {"job_id": job_id}

        def update(self, job_id, **kwargs):
            store_updates.append((job_id, dict(kwargs)))

    servicer = PicoDomeServicer(
        scan_engine=engine,
        start_time=time.time(),
        scan_count_ref=MagicMock(),
        job_store=_Store(),
        scan_slots=scan_slots,
    )

    context = _make_context()
    context.abort = MagicMock(side_effect=RuntimeError("RESOURCE_EXHAUSTED"))
    with contextlib.suppress(RuntimeError):
        servicer.Scan(_make_request(), context)

    statuses = [u[1].get("status") for u in store_updates]
    assert "failed" in statuses, f"expected 'failed' when slots exhausted, got {statuses}"

    scan_slots.release()


def test_scan_without_slots_runs_inline():
    """No scan_slots injected → scan runs inline (backwards compat)."""
    engine = MagicMock()
    engine.scan = MagicMock(return_value=_FakeSandboxResult())
    engine.analyze = MagicMock(return_value=_FakeAnalysisResult())

    servicer = PicoDomeServicer(
        scan_engine=engine,
        start_time=time.time(),
        scan_count_ref=MagicMock(),
        scan_slots=None,
    )

    result = servicer.Scan(_make_request(), _make_context())
    assert result is not None
