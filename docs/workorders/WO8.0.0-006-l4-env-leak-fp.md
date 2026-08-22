# WO8.0.0-006 — Sandbox: L4 env_leak L4-ENV-002 checks env var NAMES in network addresses (false positive)

**Series:** WO8.0.0 (exploration round 2026-08-22)
**Status:** OPEN
**Owner:** (unassigned — worktree `wo/8.0.0/l4-env-leak-fp`)
**Priority:** P2 · Effort S · Risk L
**Scope:** `picosentry/sandbox/l4/rules/env_leak.py`, `tests/sandbox/`

**Gate:** `bash scripts/test.sh fast` + test: a network call to `redis_url.cache.internal` does NOT produce L4-ENV-002; a network call whose address literally contains an env var VALUE (not name) does produce it.

## Objective
The L4-ENV-002 rule (lines 50-63) checks whether sensitive env var NAMES appear as substrings in network addresses. The intent is to detect exfiltration of env var VALUES to network endpoints, but the code checks NAMES. This produces false positives when a benign internal service hostname happens to contain an env var name (e.g. `redis_url.cache.internal` matches `REDIS_URL`). Additionally, the `or` condition at line 54 is redundant (`lower_val in lower_addr or var_name.lower() in lower_addr` — both sides are identical). The rule should check for env var VALUES being exfiltrated, not names.

## Evidence (verified 2026-08-22, read-only explorer; live repro in /tmp/opencode)
- `env_leak.py:50-63`: `for call in profile.network_calls: for var_name in SENSITIVE_ENV_VARS: ... if lower_val in lower_addr or var_name.lower() in lower_addr:`
- `env_leak.py:52-54`: `lower_val = var_name.lower()` then `if lower_val in lower_addr or var_name.lower() in lower_addr` — the two sides of `or` are identical (redundant).
- The check matches env var NAMES (e.g. `REDIS_URL`, `MONGO_URL`) as substrings in addresses — a benign connection to `redis_url.cache.internal` or `mongo_url.svc` produces a CRITICAL false positive.
- Live repro: address `"redis_url.cache.internal"` matches `REDIS_URL` (lowercase `"redis_url"` in `"redis_url.cache.internal"` -> True). Address `"REDIS_URL.host.com"` also matches.
- Note: real hostnames use hyphens not underscores, so the FP is rare in practice — but the logic is wrong and the rule is effectively dead code (it almost never fires on real exfil either, since exfil addresses don't contain env var names).

## Deliverables
1. Either remove L4-ENV-002 (if env var name-in-address is not a real exfil signal) or redesign it to check for env var VALUES in network addresses (requires correlating with the sandbox's captured env values, not just the name set).
2. Remove the redundant `or` condition at line 54.
3. Regression test: `redis_url.cache.internal` does NOT produce L4-ENV-002; a genuine env var value in an address DOES.