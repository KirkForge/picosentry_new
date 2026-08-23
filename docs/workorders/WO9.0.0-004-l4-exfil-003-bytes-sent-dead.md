# WO9.0.0-004 — Sandbox: L4-EXFIL-003 large outbound transfer detection is dead (no backend populates bytes_sent)

**Series:** WO9.0.0 (audit round 2026-08-23)
**Status:** OPEN
**Owner:** (unassigned)
**Priority:** P1 · Effort S · Risk L
**Scope:** `picosentry/sandbox/l4/rules/exfil.py`, `picosentry/sandbox/l4/profiler.py`, `tests/sandbox/`

**Gate:** `bash scripts/test.sh fast` + test: when the profiler extracts a network call with a `bytes_sent` value > 1000000, L4-EXFIL-003 fires. (Until a backend populates `bytes_sent`, the test should mock the profile directly.)

## Objective
L4-EXFIL-003 (large outbound data transfer detection) checks `total_sent = sum(c.bytes_sent for c in profile.network_calls)` and fires if `total_sent > 1000000` (1MB). But NO backend ever populates `NetworkCall.bytes_sent` — it defaults to 0 in every `NetworkCall` constructed by the profiler. So `total_sent` is always 0, and L4-EXFIL-003 NEVER fires. A malicious package that exfiltrates 100MB of data goes undetected by this rule.

The `NetworkCall` dataclass has a `bytes_sent: int = 0` field, but the profiler's `_extract_network_calls` (stdout regex) and `_extract_network_from_events` (kernel events) both construct `NetworkCall(address=addr, port=port)` without setting `bytes_sent`.

## Evidence (verified 2026-08-23, read-only explorer; live repro + grep)
- `exfil.py:39-49`: `total_sent = sum(c.bytes_sent for c in profile.network_calls)` / `if total_sent > 1000000:` — the rule.
- `models.py (l4):17`: `bytes_sent: int = 0` — defaults to 0.
- `profiler.py:65-77` (`_extract_network_from_events`): `calls.append(NetworkCall(address=addr, port=0))` — no `bytes_sent`.
- `profiler.py:291-299` (`_extract_network_calls`): `calls.append(NetworkCall(address=ip, port=port))` — no `bytes_sent`.
- grep for `bytes_sent` in all backend files: no results — no backend ever sets `bytes_sent`.
- Live repro (python3 in /tmp/opencode): `NetworkCall(address="evil.com", port=443, bytes_sent=0)` → L4-EXFIL-003: 0 findings. With `bytes_sent=2000000` → 1 finding (but no backend produces this).

## Deliverables
1. Either (a) populate `bytes_sent` from stdout (parse `sendto`/`write` byte counts from strace output — the `_parse_ip_port` function already parses strace blocks), or (b) remove L4-EXFIL-003 as dead code and document that per-call byte counting is not available with SCMP_ACT_LOG, or (c) use `profile.stdout_len` + `profile.stderr_len` as a proxy for outbound data volume (rough but non-zero).
2. Regression test: a profile with `NetworkCall(bytes_sent=2000000)` produces L4-EXFIL-003.