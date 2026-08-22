from picosentry.sandbox.l4.models import BehavioralProfile, SandboxFinding
from picosentry.sandbox.models import Severity


def detect_env_leak(
    profile: BehavioralProfile,
) -> list[SandboxFinding]:
    findings: list[SandboxFinding] = []

    for op in profile.fs_ops:
        path_lower = op.path.lower()
        if path_lower.endswith((".env", ".env.local", ".env.production")):
            findings.append(
                SandboxFinding(
                    rule_id="L4-ENV-001",
                    severity=Severity.HIGH,
                    message=f"Access to .env file ({op.operation}): {op.path}",
                    location=op.path,
                    evidence={"operation": op.operation, "path": op.path},
                )
            )

    env_dump_commands = {"env", "printenv", "set", "export"}
    for spawn in profile.spawns:
        exe_base = spawn.executable.split("/")[-1].lower()
        if exe_base in env_dump_commands:
            findings.append(
                SandboxFinding(
                    rule_id="L4-ENV-003",
                    severity=Severity.HIGH,
                    message=f"Environment dumping command spawned: {spawn.executable}",
                    location=spawn.executable,
                    evidence={"executable": spawn.executable, "args": spawn.args},
                )
            )

    return findings
