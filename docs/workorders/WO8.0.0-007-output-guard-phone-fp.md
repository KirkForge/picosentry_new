# WO8.0.0-007 — Watch: output_guard phone PII pattern false-positives on numeric data

**Series:** WO8.0.0 (exploration round 2026-08-22)
**Status:** OPEN
**Owner:** (unassigned — worktree `wo/8.0.0/output-guard-phone-fp`)
**Priority:** P1 · Effort S · Risk L
**Scope:** `picosentry/watch/output_guard/__init__.py`, `tests/watch/`

**Gate:** `bash scripts/test.sh fast` + test: a model output containing `{"size": 1234567890}` or `Duration: 123.456.7890 ms` does NOT produce `out_pii_phone`; a real phone number like `+1 (555) 123-4567` DOES.

## Objective
The output_guard phone PII pattern (lines 317-320) has a second alternative that is far too broad: `\b\+?(?:\d{1,3}[-.\s]?)?\(?\d{1,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b` matches any 10-11 digit number with optional separators. This fires on common numeric data in LLM outputs: file sizes (`1234567890`), durations (`123.456.7890`), line counts (`1234567`), numeric IDs (`12345-678901`). Each false positive produces an `out_pii_phone` violation and redacts the number, corrupting benign output and inflating the violation count. The first alternative (US phone format `\d{3}[-.\s]?\d{3}[-.\s]?\d{4}`) is specific enough; the second is the problem.

## Evidence (verified 2026-08-22, read-only explorer; live repro in /tmp/opencode)
- `output_guard/__init__.py:317-320`: `phone_pattern = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b|\b\+?(?:\d{1,3}[-.\s]?)?\(?\d{1,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b")`
- Live repro:
  - `"File size: 1234567890 bytes"` -> `['1234567890']` (FALSE POSITIVE — file size)
  - `"Duration: 123.456.7890 ms"` -> `['123.456.7890']` (FALSE POSITIVE — duration)
  - `'ID: 12345-678901'` -> `['12345-678901']` (FALSE POSITIVE — numeric ID)
  - `'Scan result: 12345 67890'` -> `['12345 67890']` (FALSE POSITIVE — counts)
  - `'{\"size\": 1234567890, \"duration_ms\": 123.456.7890}'` -> `['1234567890', '123.456.7890']` (FALSE POSITIVE on JSON output)

## Deliverables
1. Tighten the phone pattern: require at least one of (a) a leading `+` country code, (b) parentheses around the area code, or (c) a `tel:` prefix — so bare 10-digit numbers without phone-like structure are not matched. Alternatively, remove the overly-broad second alternative and keep only the US-format first alternative plus an explicit international format with `+`.
2. Regression test: assert `{"size": 1234567890}` does NOT produce `out_pii_phone`; assert `+1 (555) 123-4567` and `+44 20 7946 0958` DO.