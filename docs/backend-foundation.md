# Backend foundation: implemented scope and acceptance

This milestone implements local claim submission, persisted queued investigations,
exact-request reuse, retrieval, health, and startup interruption cleanup. It does not
execute research. No Nebius, Tavily, OpenAI SDK, or provider credentials are required.
New investigations remain queued; there is no worker, inference, search, verdict,
SSE endpoint, evidence endpoint, refresh, or comparison implementation yet.

The accepted PR #5 build order places refresh/comparison after the working minimum.
This branch starts from main; PR #5 was still open when implementation began.
Sections in the root README describing the complete agent remain design targets.

## Local setup

Requirements: Python 3.12+ and uv. Development and CI use the committed `uv.lock`.

```sh
uv sync --locked --dev
uv run --locked aletheia
```

The service binds to `http://127.0.0.1:8000` using one process. API documentation is
at `/docs`; the generated contract is at `/openapi.json`. Do not expose or tunnel this
unauthenticated service. Multiple server processes sharing this database are unsupported;
startup recovery assumes the previous server has stopped.

Runtime optionally loads `.env` in the current working directory without overriding
already-set environment variables. Do not inspect existing dotenv files. No key values
belong in documentation, tests, logs, or commits.

| Setting | Default | Validation |
| --- | --- | --- |
| `ALETHEIA_DATABASE_PATH` | `data/aletheia.sqlite3` | Persistent file path; parent directories created on startup. |
| `ALETHEIA_QUEUE_LIMIT` | `100` | Integer 1–10000; counts queued and running investigations. |
| `ALETHEIA_MAX_BODY_BYTES` | `65536` | Integer 1024–1048576; actual streamed bytes are bounded. |

Database paths are relative to the server's working directory unless absolute.
Database files, journals, environments, and test artifacts are ignored by Git.
Schema version 1 is recorded in SQLite's `user_version`; unsupported versions fail
startup without being downgraded. Future schema changes must add explicit migrations.

## API behavior

| Request | Behavior |
| --- | --- |
| `POST /investigations` | Accept `{claim, context?}`; create once or reuse the latest exact match. `202` for queued/running, `200` for existing terminal states. |
| `GET /investigations/{id}` | Read the saved record, with `reused: true`; no new work. `404` for an unknown UUID, `422` for an invalid UUID. |
| `GET /health` | Check all foundation tables; return `research_enabled: false`. No provider probes. |

Submission responses include a `Location` header and `links.self`. Links to future
endpoints are not advertised. `result` is explicitly null in the foundation contract;
typed findings/evidence results will be added with the research implementation.
Execution statuses are defined now so later research stages can extend the lifecycle.
The companion frontend branch is not part of this main-branch checkout. When it is
integrated, its provisional types must accept explicit null context fields, the
`links.self` field, and the foundation's null result; generate or reconcile them
against this backend's `/openapi.json` before connecting live mode.

Claims must contain non-whitespace text and be at most 8000 characters. Context accepts
only `timeframe`, `location`, `definitions`, and `notes`, each at most 4000 characters
or explicitly null. Unknown fields and non-string values are rejected. A null context
object is invalid; omit it or provide `{}`. Oversized bodies return `413`, validation
errors `422`, and database/queue failures `503`. Error responses do not echo submitted
values or internal database paths.

The matching key hashes outer-trimmed, Unicode-NFC claim text plus canonical JSON
context. Case, punctuation, numbers, dates, internal whitespace, and context values
are preserved. Omitted context and `{}` match; an omitted field, explicit null, and
an empty string are distinct. Original submitted text is stored without normalization.
Relative dates are not resolved here; interpretation and clarification come later.

The database transaction serializes new submissions, checks capacity, and atomically
creates the request, investigation, and sequence-1 queued event. Reuse works even when
the queue is full and appends no event. Events are persisted internally, not streamed yet.
On restart, queued records remain queued; leftover running records become failed with
an interruption reason and a terminal event in the same transaction. No work is resumed.

## Acceptance checklist

| Requirement | Automated evidence |
| --- | --- |
| Submit, retrieve, UUID/UTC, original text, self link | `test_submit_retrieve_and_duplicate` |
| Reject bad schemas without writes, enforce boundaries | `test_invalid_input_does_not_persist`, `test_request_boundaries`, `test_invalid_json_and_unknown_id` |
| Correct exact-match rules and context semantics | `test_request_identity_rules` |
| Reuse terminal states and latest version | `test_terminal_reuse_never_requeues`, `test_latest_version_reused_without_refresh_implementation` |
| Concurrent duplicates create one record/event | `test_concurrent_http_submissions`, `test_independent_connections_deduplicate` |
| Queue limit is atomic and allows existing reads/reuse | `test_capacity_is_atomic_across_connections`, `test_full_queue_reuses_existing_and_rejects_new` |
| Event failure rolls back the whole submission | `test_failed_event_rolls_back_entire_submission` |
| Reopen preserves records and identity | `test_reopen_application_preserves_queued_record` |
| Recovery is transactional and happens once | `test_recovery_is_atomic_ordered_and_idempotent` |
| Schema guard, uniqueness, non-database safety | `test_schema_version_and_unique_constraints`, `test_non_database_file_is_not_overwritten` |
| Streamed body bound cannot trust Content-Length | `test_body_limit_checks_stream_even_with_false_content_length` |
| DB health failures and errors are sanitized | `test_health_and_database_failure`, `test_sqlite_failure_redacted` |
| Settings, missing credentials, privacy | `tests/test_config.py`, `test_validation_does_not_echo_supplied_secrets` |
| No network or real dotenv access in suite | pytest-socket default settings; autouse `forbid_dotenv` fixture |

Terminal state/version fixtures simulate future stages to test retrieval and reuse;
they do not demonstrate a working research engine or valid synthesized results.

```sh
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest
```

GitHub Actions runs these checks on Python 3.12 and 3.13. The
[Aletheia Testing skill](../skills/aletheia-testing/SKILL.md) captures the repeatable
workflow. Results of review, selective fault injection, and the manual walkthrough
belong in the implementation report; do not infer their completion from this checklist.

The skill is versioned under `skills/aletheia-testing/`. For automatic discovery,
install that folder under your Codex skills directory; otherwise invoke it by its
full `SKILL.md` path. It applies only to Aletheia backend testing.

Additional opt-in checks:

```sh
uv run --locked python scripts/check_test_sensitivity.py
uv run --locked python scripts/smoke_foundation.py
```

The first introduces two deliberate faults in temporary source copies and checks
that targeted tests fail. The second starts a temporary localhost server, exercises
submission/retrieval/reuse over HTTP, restarts the process, and checks persistence.
It uses a temporary working directory and database, loads no project dotenv file,
and bypasses HTTP proxy settings for local requests. Neither script calls providers.

## Manual walkthrough

With the server running:

```sh
curl -s http://127.0.0.1:8000/health
curl -i -H 'Content-Type: application/json' \
  -d '{"claim":"Mount Everest is above sea level.","context":{"notes":"Foundation walkthrough"}}' \
  http://127.0.0.1:8000/investigations
```

1. Copy the returned `links.self` path and fetch it on the same local server.
2. Repeat the same submission: expect the same ID/timestamp and `reused: true`.
3. Stop and restart the application from the same directory and configuration.
4. Fetch the saved ID again: the record must remain queued and unchanged.
5. No verdict or research progress should appear at this milestone.
