# PR #10 review follow-up

Review disposition for the Step 2 provider adapters, November 4, 2026
(America/Los_Angeles). The PR remains based on the foundation branch and depends on
PR #8. Each numbered link points to the original review comment.

| Comment | Outcome and evidence |
| --- | --- |
| [1: oversized extraction](https://github.com/skanvish11/Aletheia-core/pull/10#discussion_r4476209896) | Fixed. One sequential request per URL isolates byte limits and retries. Oversized response bodies omit only that page; retained text has a configurable character cap and explicit truncation flag/limitation. Tests retain successful pages before and after an oversized page and check exact Unicode prefix retention. |
| [2: result at deadline](https://github.com/skanvish11/Aletheia-core/pull/10#discussion_r4476209900) | Fixed. Remove the deadline rejection after successful validation. A regression test completes validation at the deadline, retains the result, and rejects the next request without dispatch. Extraction also retains earlier pages when budget/deadline/authentication stops later work. |
| [3: measured budgets](https://github.com/skanvish11/Aletheia-core/pull/10#discussion_r4476209903) | Added 75,563-character source inputs, 40-record replies, and separately measured offline retry timing. The live 2,048-token check truncated; all six checks passed at 4,096. Implemented output default is now 4,096; proposed quick/deep model attempts are revised to 8/16, with a three-attempt/45-second finalization reserve. See the linked reports and calculations in the provider guide. |
| [4: concurrency](https://github.com/skanvish11/Aletheia-core/pull/10#discussion_r4476209907) | Explicitly deferred to the Step 3 controller: a shared maximum of two independent requests in flight. Current atomic reservations enforce usage limits, not global concurrency. Individual extraction calls are sequential. |
| [5: model settings](https://github.com/skanvish11/Aletheia-core/pull/10#discussion_r4476209914) | Clarified the supported single-model scope. Each immutable configuration binds a model, response format, and cap; there is no per-request model switch or fallback. Other models need separate verified configurations. A test checks independent models/formats/caps. A model registry is deferred until multiple-model routing exists. |
| [6: config ownership](https://github.com/skanvish11/Aletheia-core/pull/10#discussion_r4476209920) | Moved `ProviderSettings` and its explicit runtime loader into `config.py`; removed `providers/settings.py`. Foundation settings still require no provider credentials. |
| [7: sensitivity script](https://github.com/skanvish11/Aletheia-core/pull/10#discussion_r4476209927) | Retained intentionally. The Aletheia testing skill requires selected deliberate-fault checks for critical protections. Updated the two mutation targets after the refactor; both faults were detected. No general mutation framework was added. |
| [8: parser closures](https://github.com/skanvish11/Aletheia-core/pull/10#discussion_r4476209931) | Extracted module-level completion/search/extraction parsers and added direct tests requiring no HTTP transport. |
| [9: repeated switches](https://github.com/skanvish11/Aletheia-core/pull/10#discussion_r4476209939) | Subclasses pass their key and endpoint explicitly. Budget limits are built once and used to initialize matching usage counters. |
| [10: environment duplication](https://github.com/skanvish11/Aletheia-core/pull/10#discussion_r4476209944) | Runtime loading and test isolation share the exported `PROVIDER_ENV` mapping in `config.py`. |
| [11: repeated validation/reporting](https://github.com/skanvish11/Aletheia-core/pull/10#discussion_r4476209947) | Shared annotated source URL, URL-length constant, and depth definitions. Smoke checks build one measurement record for both success and failure. |
| [12: attempt naming](https://github.com/skanvish11/Aletheia-core/pull/10#discussion_r4476209952) | Renamed the loop variable to `attempt`; index zero is the original attempt. |
| [13: constructor/literals](https://github.com/skanvish11/Aletheia-core/pull/10#discussion_r4476209955) | Constructors now own meaningful endpoint/key selection. Instance methods use `self.provider`; standalone parsers and constructor setup retain the explicit provider identity they need. |
| [14: mixed responsibilities](https://github.com/skanvish11/Aletheia-core/pull/10#discussion_r4476209961) | Moved attempt/budget accounting to `budgets.py` and error vocabulary to `providers/errors.py`. Kept the small provider/operation/unit arguments explicit; an additional wrapper type would not add enforcement at this stage. |

## Validation

- `uv sync --locked --dev` created an isolated environment from the unchanged lockfile.
- `uv run --locked ruff check .` and `uv run --locked ruff format --check .` passed.
- `uv run --locked pytest -q`: **161 passed** on Python 3.15.2. The same suite also
  passed on Python 3.12.14 using the existing locked environment with `PYTHONPATH=src`.
- `uv run --locked python scripts/check_provider_test_sensitivity.py`: both deliberate
  faults detected in temporary copies, including the relocated budget implementation.
- `git diff --check` passed.
- Representative live checks used the explicitly authorized model and private runtime
  loading. No dotenv contents, credentials, response bodies, or source URLs are in the
  reports. The 2,048-token failure is retained alongside the 4,096-token successful run.
- Remote checks run after pushing; their current status is available on the PR.
  No independent agent review was requested or performed.

Tests validate provider behavior and foundation regressions. Synthetic live checks
validate connectivity, output shape, and selected limits; they do not establish
citation correctness, research quality, or a production latency guarantee.
