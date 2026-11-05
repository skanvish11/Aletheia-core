# Foundation validation report

Validated November 4, 2026 (America/Los_Angeles).

## Delivered

- Local FastAPI application, locked Python dependencies, and runtime configuration.
- SQLite schema version 1, exact-request reuse, atomic queued events, queue limits,
  saved reads, and restart interruption recovery.
- Submission, retrieval, and database health endpoints with bounded input and safe errors.
- Offline behavioral tests, GitHub Actions workflow, a reusable testing skill, and
  reproducible localhost and selective fault-injection checks.

## Observed local results

| Check | Result |
| --- | --- |
| `ruff check .` | Passed. |
| `ruff format --check .` | Passed. |
| `pytest -q` on Python 3.12.14/macOS | 57 passed; network sockets blocked except local Unix sockets required by the event loop. |
| Skill Creator `quick_validate.py skills/aletheia-testing` | Passed. |
| Duplicate lookup deliberately disabled in temporary copy | Targeted submission/reuse test failed as expected. |
| Failed transaction deliberately committed in temporary copy | Targeted atomic-submission test failed as expected. |
| Localhost HTTP walkthrough | Health, submit, retrieve, repeat submission, and new-process persistence all passed. |
| Independent agent review | No blocking defects in milestone scope. |

The independent reviewer ran the then-current 56-test suite and inspected API,
storage, configuration, contracts, CI, documentation, and the skill. Its additional
malformed-Unicode and deeply nested JSON probes received sanitized 422 responses.
Its minor embedded-NUL database-path finding was fixed and covered by the 57th test.
The skill is versioned in this repository and was installed in the user's Codex
skills directory for discovery on subsequent turns.

No actual dotenv files were opened by the implementing or reviewing agent. Tests
prevent dotenv loading and do not require real provider keys. The localhost smoke
script runs from a temporary directory without a dotenv file. No Nebius, Tavily,
or other model-provider integration was invoked.

## Limits

- New investigations remain queued. No research worker, inference, web research,
  evidence collection, factual verdicts, or research-quality evaluation exists yet.
- The result contract is null-only until typed research results are implemented.
- Persisted events are internal; SSE, evidence endpoints, refresh, and comparison
  remain future work.
- The companion frontend is on a separate branch and has not been connected or
  browser-tested against this backend.
- Startup recovery assumes one server process. Distributed/multi-process deployment
  and public access are outside this milestone.
- The two fault-injection checks are selective, not exhaustive mutation analysis.
- GitHub Actions is configured for Python 3.12 and 3.13; its actual remote outcome
  must be checked on the PR rather than inferred from local success.

These results establish the tested foundation behaviors, not absence of all defects
or accuracy of the future research agent.

## Performance follow-up

The [localhost benchmark report](benchmarks/README.md) records 14,400 measured
requests across 100, 1,000, and 10,000 synthetic saved investigations, with zero
HTTP errors or failed database-integrity assertions. The candidate fingerprint
change did not show a consistent gain across workloads and was not applied.
The unchanged backend and candidate each passed the 57-test offline suite.
The benchmark is opt-in and does not add machine-dependent latency gates to CI.
