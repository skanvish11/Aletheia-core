# PR #11 review follow-up

All ten findings from the review of `88ca859` were checked against the implementation.
This update addresses each one. Regression coverage is in
`tests/test_research_review.py`, with transaction/concurrency checks also in
`tests/test_research_integrity.py`. No live provider calls were made.

| Finding | Resolution and regression evidence |
| --- | --- |
| [1: empty initial plan](https://github.com/skanvish11/Aletheia-core/pull/11#discussion_r4476568460) | Fixed. Empty plans are valid at any round; a nonempty initial plan still requires both support and counterevidence queries. An HTTP regression verifies completed/unable-to-decide, `no_useful_query`, and zero search/extraction calls. |
| [2: failed runs cannot retry](https://github.com/skanvish11/Aletheia-core/pull/11#discussion_r4476568464) | Fixed through explicit `/refresh`, with the same required idempotency key. Failed runs expose this link and create a new version from the original request. Ordinary submission still reuses the failure without calls. Tests cover provider failure, restart interruption, concurrent retries, capacity, transaction rollback, preservation of the original failure, and an unavailable comparison when the parent has no result. |
| [3: worker stops after storage error](https://github.com/skanvish11/Aletheia-core/pull/11#discussion_r4476568473) | Fixed with bounded transactional recovery. Up to three reconciliation attempts mark interrupted running work failed with `storage_failure`; the worker then resumes queued jobs. Partially executed provider work is never replayed. Health is unavailable while recovering. A real SQLite writer lock verifies recovery, one terminal event, and subsequent successful work. A persistent-failure test verifies exactly three attempts, unavailable health, a closing SSE stream, and later shutdown recovery. |
| [4: cancellation after terminal commit](https://github.com/skanvish11/Aletheia-core/pull/11#discussion_r4476568477) | Fixed. Shutdown reconciles running rows after the task stops, rather than unconditionally finishing the current ID from the cancellation handler. Tests cancel immediately after a terminal commit and after a claim commit: the former retains its result and one terminal event; the latter is marked interrupted once. |
| [5: extraction errors mislabeled not selected](https://github.com/skanvish11/Aletheia-core/pull/11#discussion_r4476568479) | Fixed. An absent source with any `source_rejected` event is a retrieval failure. Refresh tests cover timeout, rate limit, network, unavailable, oversized response, invalid response, and historical `page_size_limit` reasons. Existing extraction-failure coverage remains. |
| [6: hard-coded page-size rejection](https://github.com/skanvish11/Aletheia-core/pull/11#discussion_r4476568481) | Fixed by honoring the provider's validated configurable prefix limit without a second 100,000-character rejection. At a 200,000-character limit, tests retain a 150,000-character page intact and a 210,000-character page as the exact flagged prefix. Assessment input limits still apply. |
| [7: finalization reserve too small](https://github.com/skanvish11/Aletheia-core/pull/11#discussion_r4476568485) | Fixed: reserve four model attempts within the unchanged 8/16 totals. A test exhausts research capacity and successfully repairs both synthesis and explanation checking. Deliberately restoring a three-call reserve makes that test fail. The 45-second reserve is unchanged; neither attempts nor time guarantee completion under additional transport retries or exhausted deadlines. |
| [8: SSE repeatedly parses full history](https://github.com/skanvish11/Aletheia-core/pull/11#discussion_r4476568489) | Fixed with `sequence > cursor` in SQLite. Tests prove earlier payloads are not parsed, header precedence remains intact, oversized SQL cursors are rejected, and a worker finishing between the event read and stop check does not lose its terminal event. The existing sequence index supports the query; polling still performs a separate status read. |
| [9: evidence endpoint loads full snapshots](https://github.com/skanvish11/Aletheia-core/pull/11#discussion_r4476568498) | Fixed with a SQLite JSON metadata projection and a dedicated metadata model. The HTTP test forbids full Snapshot validation and verifies identical public metadata. SQLite still reads/traverses the stored JSON; this avoids transferring page bodies/spans into Python and validating them on every metadata read. No schema migration or duplicate metadata store is introduced. |
| [10: health without lifespan](https://github.com/skanvish11/Aletheia-core/pull/11#discussion_r4476568503) | Fixed with initialized application state and a 503 response before lifespan initialization. Tests deliberately omit lifespan with an existing database in both research-enabled and disabled configurations. Normal tests still enter lifespan explicitly. |

## Validation and limits

- `uv run --locked pytest -q`: **269 passed** on Python 3.12, offline. This adds
  25 cases beyond the previously passing 244-test suite.
- Ruff lint/format and `git diff --check`: passed.
- `scripts/check_research_test_sensitivity.py` detects six deliberate faults,
  including the insufficient finalization reserve and disabled explicit retry.
- Provider attempts remain bounded and offline tests cannot access the network.
- Application/prompt versions advance to `research-v3` / `one-claim-v3` so future
  comparisons can identify these behavior changes. Existing records are retained.
- No independent agent review, live research evaluation, or new latency benchmark
  was performed. Permanent database unavailability still requires restart after
  bounded recovery fails; it is reported explicitly rather than retried forever.

PR #13 has merged the reviewed Step 2 adapters into main. PR #11 now targets main
and remains subject to
review of these changes and the previously documented live-evaluation gates.
