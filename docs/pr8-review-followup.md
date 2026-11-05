# PR #8 review follow-up

Six actionable findings are fixed. Two findings describe intentional Step 1
limitations, and two suggestions remain optional. These dispositions do not claim
that the research worker or explicit refresh already exists.

| Finding | Disposition | Change or remaining work |
| --- | --- | --- |
| 1. Queue eventually fills without a worker | Documented milestone limitation | The default 100 queued records persist across restarts. Step 3 adds the worker. Reads/reuse still work when full; use a separate disposable database for experiments. No silent deletion or eviction. |
| 2. Interrupted/failed requests are reused | Documented contract; future feature | Exact resubmission returns saved history. Explicit retry/refresh must create a new version and needs its own idempotency rules and tests; it remains a follow-up after the minimum agent works. |
| 3. Benchmark SQLite handles stay open | Fixed | Explicit connection closing retains commit/rollback behavior and releases handles on assertion failure, supporting temporary-directory cleanup on Windows. |
| 4. Default body cap rejects allowed Unicode input | Fixed | Default increased from 64 KiB to 320 KiB. Regression tests submit every field at its character limit using raw and escaped non-BMP Unicode; excess total bytes still return 413. |
| 5. Context strings are not NFC-normalized | Optional policy change | The current contract normalizes claims only and preserves context values. Changing this requires a documented matching policy, collision/duplicate decisions, and migration of persisted matching keys. It is not a prerequisite for Step 2. |
| 6. Smoke startup misses transient disconnects | Fixed | Readiness retries remote disconnects and connection resets/aborts as well as timeout/URL failures, with a bounded attempt count. |
| 7. Temporary-port probe has a release/rebind race | Fixed | Both scripts share a child-owned socket bound to port 0 and retained while serving; every restart publishes its actual address. |
| 8. Initialization adopts unrelated SQLite databases | Fixed | Refuse nonempty unversioned schemas and mismatched version-1 schemas before mutations. Tests cover unrelated/colliding tables, view-only databases, and names resembling SQLite's internal prefix; rejected database bytes remain unchanged. Original V1 databases still reopen. |
| 9. Rollback mutation changes several methods | Fixed | Select `Storage.submit` using the Python syntax tree and require exactly one target inside that method; initialization/recovery remain untouched. Missing or ambiguous targets fail closed. |
| 10. Repeated transaction handling | Optional cleanup | A helper may reduce duplication later if it makes ownership clearer. Preserve locking, commit/rollback, cancellation, and error sanitization; rerun transaction/recovery regressions if refactored. No demonstrated correctness defect requires it now. |

## Validation

- 80 offline tests pass locally on Python 3.12, including 23 new review regressions.
- Both deliberate-fault checks still detect the intended duplicate and rollback bugs.
- Localhost submit/retrieve/reuse and restart persistence pass with the new socket lifecycle.
- A small synthetic run at 100, 1,000, and 10,000 saved records passes response and
  database-integrity assertions. It is a correctness check, not a new latency baseline.
- CI retains Python 3.12/3.13 offline checks and adds Linux/Windows localhost and
  benchmark cleanup checks. Consult the PR checks for the actual remote results.
- No provider calls or real dotenv access are required for these fixes or checks.

The [foundation contract](backend-foundation.md) defines implemented behavior;
the [validation report](foundation-validation.md) preserves earlier evidence and
records this review follow-up separately.
