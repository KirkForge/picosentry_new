"""Unit tests for LogManager exception-narrowing paths."""

from __future__ import annotations

import logging
import os
import stat
from pathlib import Path

import pytest

from picosentry.serve.services.log_manager import LogManager


class TestLogManagerHardening:
    """Log query must tolerate expected file errors but surface programmer errors."""

    def test_oserror_while_reading_log_is_logged_and_skipped(self, tmp_path, caplog, monkeypatch):
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "app.log").write_text("INFO hello\n", encoding="utf-8")

        manager = LogManager(log_dir=str(log_dir))

        def _boom(*args, **kwargs):
            raise OSError("permission denied")

        monkeypatch.setattr(Path, "open", _boom)

        with caplog.at_level(logging.WARNING, logger="picoshogun.LogManager"):
            entries = manager.query()

        assert entries == []
        assert any("Failed to read log file" in r.message for r in caplog.records)

    def test_unicode_decode_error_while_reading_log_is_logged_and_skipped(self, tmp_path, caplog):
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "app.log").write_bytes(b"\xff\xfe\x00\x00")  # invalid UTF-8

        manager = LogManager(log_dir=str(log_dir))

        with caplog.at_level(logging.WARNING, logger="picoshogun.LogManager"):
            entries = manager.query()

        assert entries == []
        assert any("Failed to read log file" in r.message for r in caplog.records)

    def test_unexpected_error_while_reading_log_propagates(self, tmp_path, monkeypatch):
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "app.log").write_text("INFO hello\n", encoding="utf-8")

        manager = LogManager(log_dir=str(log_dir))

        def _boom(*args, **kwargs):
            raise AttributeError("programmer mistake")

        monkeypatch.setattr(Path, "open", _boom)

        with pytest.raises(AttributeError, match="programmer mistake"):
            manager.query()


class TestLogManagerReadOnlyFs:
    """WO8.0.0-101: LogManager must not crash on a read-only filesystem.

    The serve helm chart sets readOnlyRootFilesystem: true; the module-level
    singleton ``LogManager()`` runs at import time and used to call
    ``mkdir(parents=True, exist_ok=True)`` unconditionally, crashing the
    container before it started. The guard degrades to console-only logging.
    """

    def test_mkdir_on_readonly_dir_does_not_raise(self, tmp_path, caplog):
        ro = tmp_path / "readonly"
        ro.mkdir()
        os.chmod(ro, stat.S_IRUSR | stat.S_IXUSR)
        try:
            with caplog.at_level(logging.WARNING, logger="picoshogun.LogManager"):
                manager = LogManager(log_dir=str(ro / "logs"))
            assert not manager.log_dir.exists()
            assert any("not writable" in r.message for r in caplog.records)
        finally:
            os.chmod(ro, stat.S_IRWXU)

    def test_query_and_stats_safe_when_dir_missing(self, tmp_path):
        manager = LogManager(log_dir=str(tmp_path / "never-created"))
        assert manager.query() == []
        stats = manager.get_stats()
        assert stats["file_count"] == 0
        assert stats["directory"] == str(tmp_path / "never-created")


class TestSettingsLogBackupDirEnvOverride:
    """WO8.0.0-101: PICOSHOGUN_LOG_DIR / PICOSHOGUN_BACKUP_DIR env overrides."""

    def test_log_dir_env_override(self, monkeypatch):
        from picosentry.serve.config.settings import LoggingConfig

        monkeypatch.setenv("PICOSHOGUN_LOG_DIR", "/custom/log/path")
        cfg = LoggingConfig()
        assert cfg.log_dir == Path("/custom/log/path")

    def test_backup_dir_env_override(self, monkeypatch):
        from picosentry.serve.config.settings import DatabaseConfig

        monkeypatch.setenv("PICOSHOGUN_BACKUP_DIR", "/custom/backup/path")
        cfg = DatabaseConfig()
        assert cfg.backup_dir == Path("/custom/backup/path")

    def test_defaults_preserved_when_env_unset(self, monkeypatch):
        from picosentry.serve.config.settings import BASE_DIR, DatabaseConfig, LoggingConfig

        monkeypatch.delenv("PICOSHOGUN_LOG_DIR", raising=False)
        monkeypatch.delenv("PICOSHOGUN_BACKUP_DIR", raising=False)
        assert LoggingConfig().log_dir == BASE_DIR / "logs"
        assert DatabaseConfig().backup_dir == BASE_DIR / "backups"


class TestConfigureLoggingReadOnlyFs:
    """WO8.0.0-101: configure_logging degrades to console-only on read-only FS."""

    def test_readonly_log_dir_falls_back_to_console_only(self, tmp_path):
        from logging.handlers import RotatingFileHandler

        from picosentry.serve.config.logging_config import configure_logging

        ro = tmp_path / "readonly"
        ro.mkdir()
        os.chmod(ro, stat.S_IRUSR | stat.S_IXUSR)
        try:
            configure_logging(level="INFO", log_dir=ro / "logs", structured=True)
            root = logging.getLogger()
            handlers = root.handlers
            assert any(isinstance(h, logging.StreamHandler) for h in handlers)
            assert not any(isinstance(h, RotatingFileHandler) for h in handlers)
        finally:
            os.chmod(ro, stat.S_IRWXU)
            logging.getLogger().handlers.clear()
