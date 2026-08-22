"""WO8.0.0-009: L4 profiler emits rich operation types (create/delete/chmod/chown) from events."""

from __future__ import annotations

from picosentry.sandbox.l3.models import SandboxEvent, SandboxResult, Verdict
from picosentry.sandbox.l4.profiler import _extract_fs_from_events, profile_from_sandbox_result


def _event(operation: str, path: str, detail: str = "") -> SandboxEvent:
    return SandboxEvent(
        rule_id="L3-FS-001",
        verdict=Verdict.DENY,
        operation=operation,
        detail=detail or f"{operation}: {path}",
        path=path,
    )


def _result(events: list[SandboxEvent]) -> SandboxResult:
    return SandboxResult(
        command=["node", "evil.js"],
        overall_verdict=Verdict.ALLOW,
        exit_code=0,
        duration_ms=100,
        events=events,
        stdout="",
        stderr="",
    )


def test_file_save_is_create():
    ops = _extract_fs_from_events([_event("file_save", "/etc/cron.d/evil")])
    assert len(ops) == 1
    assert ops[0].operation == "create", f"file_save → create, got {ops[0].operation}"
    assert ops[0].path == "/etc/cron.d/evil"


def test_file_export_is_create():
    ops = _extract_fs_from_events([_event("file_export", "/tmp/evil.bin")])
    assert len(ops) == 1
    assert ops[0].operation == "create"


def test_file_write_indicator_is_write():
    ops = _extract_fs_from_events([_event("file_write_indicator", "/etc/shadow")])
    assert len(ops) == 1
    assert ops[0].operation == "write"


def test_file_write_bytes_is_write():
    ops = _extract_fs_from_events([_event("file_write_bytes", "/tmp/log")])
    assert len(ops) == 1
    assert ops[0].operation == "write"


def test_file_read_is_read():
    ops = _extract_fs_from_events([_event("file_read", "/etc/passwd")])
    assert len(ops) == 1
    assert ops[0].operation == "read"


def test_file_chmod_is_chmod():
    ops = _extract_fs_from_events([_event("file_chmod", "/usr/bin/sudo")])
    assert len(ops) == 1
    assert ops[0].operation == "chmod"


def test_file_chown_is_chown():
    ops = _extract_fs_from_events([_event("file_chown", "/etc/passwd")])
    assert len(ops) == 1
    assert ops[0].operation == "chown"


def test_file_delete_is_delete():
    ops = _extract_fs_from_events([_event("file_delete", "/etc/passwd")])
    assert len(ops) == 1
    assert ops[0].operation == "delete"


def test_file_create_is_create():
    ops = _extract_fs_from_events([_event("file_create", "/tmp/new")])
    assert len(ops) == 1
    assert ops[0].operation == "create"


def test_save_to_cron_triggers_privesc_005():
    """file_save to /etc/cron.d/ → 'create' op → L4-PRIVESC-005 fires."""
    from picosentry.sandbox.l4.rules.privilege_escalation import detect_privilege_escalation

    profile = profile_from_sandbox_result(_result([_event("file_save", "/etc/cron.d/evil")]))
    assert any(op.operation == "create" for op in profile.fs_ops)
    findings = detect_privilege_escalation(profile)
    assert any(f.rule_id == "L4-PRIVESC-005" for f in findings), "file_save→create must trigger PRIVESC-005"


def test_chmod_triggers_privesc_003():
    """file_chmod event → 'chmod' op → L4-PRIVESC-003 fires for setuid patterns."""
    from picosentry.sandbox.l4.rules.privilege_escalation import detect_privilege_escalation

    profile = profile_from_sandbox_result(_result([_event("file_chmod", "chmod 4755 /usr/bin/custom")]))
    assert any(op.operation == "chmod" for op in profile.fs_ops)
    findings = detect_privilege_escalation(profile)
    assert any(f.rule_id == "L4-PRIVESC-003" for f in findings), "file_chmod→chmod must trigger PRIVESC-003"


def test_delete_triggers_fs_003():
    """file_delete event → 'delete' op → L4-FS-003 fires for critical paths."""
    from picosentry.sandbox.l4.rules.filesystem import detect_filesystem_anomalies

    profile = profile_from_sandbox_result(_result([_event("file_delete", "/etc/passwd")]))
    assert any(op.operation == "delete" for op in profile.fs_ops)
    findings = detect_filesystem_anomalies(profile)
    assert any(f.rule_id == "L4-FS-003" for f in findings), "file_delete→delete must trigger FS-003"


def test_create_triggers_persist_001():
    """file_save → 'create' op → L4-PERSIST-001 fires for persistence paths."""
    from picosentry.sandbox.l4.rules.persistence import detect_persistence

    profile = profile_from_sandbox_result(_result([_event("file_save", "/etc/systemd/system/evil.service")]))
    assert any(op.operation == "create" for op in profile.fs_ops)
    findings = detect_persistence(profile)
    assert any(f.rule_id == "L4-PERSIST-001" for f in findings), "file_save→create must trigger PERSIST-001"
