"""WO8.0.0-105: _assert_job_in_org must fall back to DB, not in-memory dict only.

In multi-worker mode, a job created on worker A is not in worker B's
in-memory dict until _converge_jobs reloads from the DB (every 30s).
Before this fix, enable/disable/trigger/delete returned 404 from worker
B even though the job existed in the shared DB.
"""

from __future__ import annotations

import time

from picosentry.serve.database.manager import DatabaseManager
from picosentry.serve.services import scheduler as sched_mod
from picosentry.serve.services.scheduler import JobScheduler


class TestAssertJobInOrgDBFallback:
    def _make_pair(self, tmp_path, monkeypatch):
        """Two scheduler instances sharing one DB (simulates two workers)."""
        mgr = DatabaseManager(db_path=tmp_path / "cross-worker.db")
        monkeypatch.setattr(sched_mod, "db", mgr)

        worker_a = JobScheduler()
        job_id = worker_a.add_job(
            name=f"cross_{time.time_ns()}", cron="0 2 * * *", command="backup", params={}, enabled=True, org_id=42
        )

        # Worker B boots fresh from the same DB but has NOT converged yet —
        # simulate by removing the job from its in-memory dict.
        worker_b = JobScheduler()
        worker_b.jobs.pop(job_id, None)
        assert job_id not in worker_b.jobs, "test setup: job must be absent from worker B"
        return worker_a, worker_b, job_id, mgr

    def test_assert_falls_back_to_db_for_job_in_other_worker(self, tmp_path, monkeypatch):
        from picosentry.serve.api.routers import scheduler as router_mod

        _, worker_b, job_id, mgr = self._make_pair(tmp_path, monkeypatch)
        monkeypatch.setattr(router_mod, "scheduler", worker_b)

        # Must NOT raise 404 — job exists in DB even if not in worker_b.jobs.
        router_mod._assert_job_in_org(job_id, 42)

        # After the DB fallback, the job is reloaded into memory.
        assert job_id in worker_b.jobs
        mgr.close()

    def test_assert_404_for_wrong_org_via_db_fallback(self, tmp_path, monkeypatch):
        import pytest
        from fastapi import HTTPException

        from picosentry.serve.api.routers import scheduler as router_mod

        _, worker_b, job_id, mgr = self._make_pair(tmp_path, monkeypatch)
        monkeypatch.setattr(router_mod, "scheduler", worker_b)

        with pytest.raises(HTTPException) as exc:
            router_mod._assert_job_in_org(job_id, 99)
        assert exc.value.status_code == 404
        mgr.close()

    def test_assert_404_for_nonexistent_job(self, tmp_path, monkeypatch):
        import pytest
        from fastapi import HTTPException

        from picosentry.serve.api.routers import scheduler as router_mod

        mgr = DatabaseManager(db_path=tmp_path / "cross-worker-404.db")
        monkeypatch.setattr(sched_mod, "db", mgr)
        worker = JobScheduler()
        monkeypatch.setattr(router_mod, "scheduler", worker)

        with pytest.raises(HTTPException) as exc:
            router_mod._assert_job_in_org(999999, 1)
        assert exc.value.status_code == 404
        mgr.close()

    def test_enable_job_on_worker_b_after_db_fallback(self, tmp_path, monkeypatch):
        from picosentry.serve.api.routers import scheduler as router_mod

        worker_a, worker_b, job_id, mgr = self._make_pair(tmp_path, monkeypatch)
        monkeypatch.setattr(router_mod, "scheduler", worker_b)

        # Simulate the router flow: assert (DB fallback + reload) then enable.
        router_mod._assert_job_in_org(job_id, 42)
        assert worker_b.enable_job(job_id)

        # Cleanup
        worker_a.remove_job(job_id)
        mgr.close()

    def test_trigger_job_on_worker_b_after_db_fallback(self, tmp_path, monkeypatch):
        from picosentry.serve.api.routers import scheduler as router_mod

        worker_a, worker_b, job_id, mgr = self._make_pair(tmp_path, monkeypatch)
        monkeypatch.setattr(router_mod, "scheduler", worker_b)

        router_mod._assert_job_in_org(job_id, 42)
        # trigger_job dispatches; stub _dispatch_job to avoid real execution.
        dispatched: list[int] = []
        monkeypatch.setattr(worker_b, "_dispatch_job", lambda jid: dispatched.append(jid))
        assert worker_b.trigger_job(job_id)
        assert dispatched == [job_id]

        worker_a.remove_job(job_id)
        mgr.close()
