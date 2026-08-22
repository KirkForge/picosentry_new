"""WO8.0.0-103: scheduler last_run / next_run must be tz-aware UTC, not naive local.

The scheduler used naive ``datetime.now()`` in 5 sites; every other service is
UTC-consistent. On a non-UTC server the stored ``last_run`` and cron
``next_run`` would drift by the local offset.
"""

from __future__ import annotations

from datetime import timezone

from picosentry.serve.database.manager import DatabaseManager
from picosentry.serve.services import scheduler as sched_mod
from picosentry.serve.services.scheduler import JobScheduler


class TestSchedulerUsesUTC:
    def test_get_next_run_returns_tz_aware(self):
        s = JobScheduler.__new__(JobScheduler)
        result = s._get_next_run("*/5 * * * *")
        assert result is not None
        assert result.tzinfo is not None, "croniter-based next_run must be tz-aware"

    def test_get_next_run_every_expression_is_tz_aware(self, monkeypatch):
        from picosentry.serve.services import scheduler as mod

        monkeypatch.setattr(mod, "HAS_CRONITER", False)
        s = JobScheduler.__new__(JobScheduler)
        result = s._get_next_run("every 5 minutes")
        assert result is not None
        assert result.tzinfo is not None, "fallback next_run must be tz-aware"

    def test_last_run_is_utc_after_execute(self, tmp_path, monkeypatch):
        mgr = DatabaseManager(db_path=tmp_path / "sched-utc.db")
        monkeypatch.setattr(sched_mod, "db", mgr)
        s = sched_mod.JobScheduler()

        job_id = s.add_job(name="utc_job", cron="0 2 * * *", command="backup", params={}, enabled=False)
        s._execute_job(job_id)

        job = s.jobs[job_id]
        assert job.last_run is not None
        assert job.last_run.tzinfo is not None, "last_run must be tz-aware UTC"
        assert job.last_run.tzinfo.utcoffset(job.last_run) == timezone.utc.utcoffset(job.last_run)

        row = mgr.execute_one("SELECT last_run FROM scheduled_jobs WHERE id = ?", (job_id,))
        assert row is not None
        stored = row["last_run"]
        if isinstance(stored, str):
            assert "+" in stored or "Z" in stored, f"stored last_run must carry tz: {stored!r}"
        mgr.close()
