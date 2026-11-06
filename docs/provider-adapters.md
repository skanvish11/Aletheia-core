# Step 2: provider connections

> This document records the earlier milestone. [Step 3](research-pipeline.md) adds
> opt-in research execution, saved evidence/results, refresh, comparisons and progress.
> Its scope document describes current behavior and the schema-3 migration.

The backend can now make explicit, bounded calls to Nebius for structured model
responses and to Tavily for search and page extraction. Both integrations passed
live checks on November 4, 2026 (America/Los_Angeles).

Claim submission still saves queued investigations. There is no worker or research
pipeline yet: health, submission, and saved reads make no provider calls. Step 3
will connect interpretation, planning, research, and evidence-linked conclusions.

## Implementation

| File | Responsibility |
| --- | --- |
| `src/aletheia/config.py` | Foundation and provider settings, runtime loading, and secret wrappers. |
| `src/aletheia/budgets.py` | Shared attempt limits, deadline, and safe attempt records. |
| `src/aletheia/providers/errors.py` | Safe provider error vocabulary. |
| `src/aletheia/providers/common.py` | HTTP lifecycle, strict JSON decoding, retries, deadlines, and size limits. |
| `src/aletheia/providers/nebius.py` | Non-streaming structured inference and strict local validation. |
| `src/aletheia/providers/tavily.py` | Search metadata and full-page extraction with ordered per-URL outcomes. |
| `scripts/smoke_providers.py` | Opt-in live integration checks and safe latency/usage reports. |

HTTPX is now a locked runtime dependency. Direct HTTP avoids SDK-internal retries
that could escape our accounting. HTTPS endpoints are fixed to the two official
services. Redirects and environment proxy discovery are disabled. Providers are
async context managers; callers close them after use.

The adapter checks response structure. Callers in Step 3 will check meaning,
assertion IDs, source references, and evidence sufficiency. Malformed model output
does not trigger hidden repair calls here; the future task/controller must budget
and explicitly request the permitted repair.

## Configuration

Foundation `Settings` remains independent of `ProviderSettings`. The local API
requires no provider credentials. `ProviderSettings.from_environment()` reads
process settings only. An explicit `dotenv_path` enables private runtime loading
from that exact file; existing environment values win. Never inspect, print,
copy, or commit a real settings file or its credentials.

| Environment setting | Default | Meaning |
| --- | --- | --- |
| `NEBIUS_API_KEY` | unset | Required when constructing the Nebius connection. |
| `TAVILY_API_KEY` | unset | Required when constructing the Tavily connection. |
| `NEBIUS_MODEL` | unset | Exact available model ID; no guessed model or automatic fallback. |
| `ALETHEIA_NEBIUS_RESPONSE_FORMAT` | `json_schema` | `json_schema` or explicitly selected `json_object`; both require local validation. |
| `ALETHEIA_PROVIDER_TIMEOUT_SECONDS` | `45` | Maximum seconds per attempt, clipped to the caller's remaining time; range 1–120. |
| `ALETHEIA_PROVIDER_MAX_RETRIES` | `2` | Maximum additional transient-error attempts; range 0–2. |
| `ALETHEIA_PROVIDER_MAX_REQUEST_BYTES` | `262144` | Encoded request limit, including instructions and schema; range 1024–1048576. |
| `ALETHEIA_PROVIDER_MAX_RESPONSE_BYTES` | `2097152` | Decoded response limit; range 1024–10485760. |
| `ALETHEIA_MAX_EXTRACTED_CHARS` | `100000` | Maximum retained characters per page; range 1024–1000000. Longer pages retain a marked prefix. |
| `ALETHEIA_MODEL_MAX_OUTPUT_TOKENS` | `4096` | Model output cap; range 64–16384. A call may request a lower cap. |

Each immutable `ProviderSettings` instance binds one exact model to its response
format and output cap. A provider cannot switch models per request or silently fall
back. Construct a separate validated settings/provider instance to use another model;
verify that model's supported format and suitable cap explicitly. The 4,096-token
starting cap is measured for the selected Nemotron model, not a compatibility promise
for other models. Tests exercise two independent model configurations.

Secret fields are excluded from settings representations and masked in JSON
serialization. Public errors and attempt records contain no remote response body,
prompt, source text, request headers, or key values. Provider response content is
returned to the caller as data, never logged by these modules. Do not log whole
request/response objects or enable HTTP wire tracing with real credentials.

## Operations and limits

`NebiusProvider.generate()` accepts instructions, input text, a Pydantic response
model, and a shared `CallBudget`. It returns the validated value and token usage
when provided. Use response models with `extra="forbid"` and explicit field bounds.
Refusals, truncation, invalid JSON, duplicate JSON keys, invalid numeric constants,
wrong field types, and malformed envelopes fail explicitly. Truncation is not
silently accepted or repaired.

`TavilyProvider.search()` accepts a nonblank query of at most 400 characters,
1–20 results, and an explicit basic/advanced depth (advanced by default). It disables
generated answers, raw page content, and automatic parameter selection. Results
retain URLs, titles, snippets, relevance scores, optional publication dates, and
the local retrieval time. Missing publication dates remain unknown. Zero results
is a successful search, distinct from a failed request.

`TavilyProvider.extract()` accepts 1–20 distinct HTTP(S) URLs without embedded
credentials and a basic/advanced depth. It requests complete Markdown rather than
query-selected chunks, using one sequential HTTP request per URL. This costs more
round trips than batching but isolates the response byte cap and retries to one page.
Results follow input URL order. Text within `max_extracted_chars` is preserved exactly;
longer text retains the exact prefix with `truncated=True` and a
`page_text_truncated` limitation. A response exceeding the byte cap is omitted with
`response_too_large` and `page_omitted`; other successful pages survive.

Failed, empty, missing, malformed, or ambiguous page responses have explicit per-URL
errors. Budget, deadline, authentication, configuration, and quota failures stop new
page requests; remaining URLs are marked `page_not_attempted`. Other page failures
allow subsequent URLs within the budget. Caller cancellation still propagates.
Invalid caller inputs raise `ProviderError` before any request. Usage credits are
summed only when every page result supplies them; otherwise usage is unknown rather
than an understated total. Failed retry charges may still be unreported by the provider. Search snippets and extracted text remain separate types.

Every operation requires a `CallBudget` with model, query, and extraction-attempt
ceilings and an absolute `time.monotonic()` deadline. Share the same object across
one investigation; do not recreate it per call. Reservations happen before dispatch
without yielding, so concurrent coroutines on one event loop cannot overspend.
Extraction charges one attempt per requested URL, including failed URLs and retries.
**Explicit Step 3 deferrals:** the controller must implement the shared two-in-flight
limit for independent queries/extractions and the research/finalization reserves.
Atomic budget reservations already prevent overspending, but they do not limit
concurrent HTTP requests. Individual extraction calls currently process pages
sequentially; independently created calls are not globally throttled.

Transient timeouts, network errors, HTTP 429, and selected temporary service errors
can retry. Authentication, invalid requests, quota errors, malformed output, and
refusals do not. Backoff honors `Retry-After` in seconds or HTTP-date form. If the
wait cannot fit, return the provider failure without retrying early. In-flight
requests are cancelled at the shared deadline; cancellation is preserved. A fully
received and validated response is retained if synchronous validation crosses the
deadline; the next attempt is blocked. The controller can then persist the usable
partial result. Each attempt records its provider, operation, units, elapsed time, HTTP status if known,
and safe outcome, including failures. No database transaction surrounds a call.

## Reproduce validation

```sh
uv sync --locked --dev
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest
uv run --locked python scripts/check_provider_test_sensitivity.py
```

The default tests block external connections and real dotenv access, clear provider
environment variables, and use synthetic credentials plus HTTP-level fixtures.
The sensitivity check deliberately breaks budget enforcement and strict validation
in temporary source copies, then requires the targeted tests to fail.

Local verification for the review revision is recorded in
[PR #10 follow-up](pr10-review-followup.md). The sensitivity script is deliberately
retained: the project's Aletheia testing skill requires selected deliberate-fault
checks for critical protections. It uses two targeted mutations, not a general
mutation-testing framework, and never changes the working source tree.

The live script makes no calls or dotenv reads without `--live`. Supply your exact
runtime settings file and a verified model. For example, with keys already in the
process environment:

```sh
uv run --locked python scripts/smoke_providers.py --live \
  --model nvidia/Nemotron-3_5-Lightning --samples 2 \
  --profile representative --max-output-tokens 4096 \
  --output provider-check.json
```

To load a private file at runtime, add `--dotenv /absolute/path/to/your/settings-file`.
The script never prints or copies that file. `--model` overrides the model setting
for this invocation only. The output must be a new file. Reports contain safe
measurements, not prompts, response bodies, source URLs, or credentials.

With two samples, the script performs four model calls, one advanced search, and
one basic extraction. It permits at most one additional model attempt, one
additional search attempt, and one additional extraction attempt under a shared
180-second deadline. It stops further model samples on a model error. Samples
are limited to 1–3; the deadline is configurable from 30–300 seconds. `--profile representative` replaces the short tasks with a 400-record input (75,563 characters)
and a 40-record structured reply. `--max-output-tokens` explicitly selects 2,048 or
4,096; otherwise the configured cap is used, bounded above by 4,096 for this script.
The representative report also includes a separate, offline retry timing exercise:
two simulated HTTP 503s then success, real 0.25/0.5-second backoff, and simulated
0.1-second service times. No artificial failures are sent to live providers.

## Acceptance evidence

| Requirement | Evidence |
| --- | --- |
| Correct authenticated requests and strict model output | `tests/test_providers.py`, live structured responses. |
| Search results, metadata, and empty-result semantics | `tests/test_providers.py`, live search. |
| Partial, missing, empty, oversized, truncated, and untraceable pages | `tests/test_providers.py`, live successful extraction. |
| Safe errors and credential handling | `tests/test_providers.py`, `tests/test_provider_limits.py`. |
| Bounded retries, deadlines, cancellation, and shared budgets | `tests/test_providers.py`, deliberate budget-fault check. |
| Input/output limits and stream cleanup | `tests/test_provider_limits.py`. |
| Live workflow is opt-in and reports safely | `tests/test_provider_smoke.py`. |
| Foundation behavior still works offline | Full repository test suite. |

### Live results — November 4, 2026

Model: `nvidia/Nemotron-3_5-Lightning`, verified in the authenticated model list.
Its published rate was $0.06 per million input tokens and $0.24 per million output
tokens, tied with Nemotron Nano at the lowest text-generation rate verified for
this check. Pricing/access can change; this is not a permanent model default.

| Operation | Successful samples | Observed duration |
| --- | ---: | --- |
| Short structured response | 2 | 2.96–3.27 seconds |
| Longer structured response (12 records) | 2 | 4.19–4.80 seconds |
| Advanced search | 1 | 0.92 seconds |
| Page extraction | 1 | 0.53 seconds; 6,765 characters |

The successful batch used 610 input and 4,012 completion tokens, approximately
$0.001 per published model rates, plus two reported Tavily search credits and zero
reported extraction credits. This is an estimate, not an invoice. Completion
usage can include reasoning tokens, so short visible replies can still use many tokens.

The initial live run caught a documentation mismatch: the narrative Nebius guide
passes the JSON schema directly, but the deployed API requires a `name`/`schema`
wrapper. The first model request returned HTTP 422. The wrapper was corrected,
covered by the wire-contract test, and all six checks then passed. The initial
Tavily search and extraction also passed (3.03 and 0.17 seconds), using two reported
search credits. Both safe reports are retained under `docs/provider-checks/`.

The original small checks needed no transient retries. The review follow-up below
adds source-heavy inputs, larger outputs, and separately measured offline retries.
Neither synthetic profile establishes research accuracy or tail latency.

### Review follow-up measurements — November 4, 2026

The representative profile uses a 400-record catalog (75,563 input characters,
16,000 prompt tokens) with an exact-record lookup, plus a 40-record output checked
against all expected values. These are larger synthetic workloads, not research
quality tests. Reports use UTC timestamps; the local date was November 4.

| Check | At 2,048 output tokens | At 4,096 output tokens |
| --- | --- | --- |
| Source-heavy input | Passed once, 8.12 s | Passed twice, 10.36–10.67 s |
| 40-record structured output | Truncated at 7.82 s; remaining model samples stopped | Passed twice, 8.37–9.29 s |
| Advanced search | Passed, 4.27 s | Passed, 2.26 s |
| One-page extraction | Passed, 0.43 s | Passed, 0.77 s |
| Offline 503/503/success exercise | 1.065 s | 1.058 s |

The two successful larger replies consumed 2,158 and 2,557 completion tokens,
including model reasoning. The successful 4,096-cap run used 32,404 input and
8,259 completion tokens. Both Tavily runs reported two search credits and zero
extraction credits. Usage for the truncated reply is unavailable in this report;
these totals must not be treated as the total bill for both runs.

No live transient failure occurred. Offline timing includes three simulated
0.1-second responses plus actual 0.25/0.5-second sleeps. It verifies elapsed retry
accounting, not live outage recovery speed. The earlier HTTP 422 and the truncation
remain failures, not successful samples. Reproduce both profiles with the script;
safe reports are committed as [2,048-cap evidence](provider-checks/2026-11-04-representative-2048.json)
and [4,096-cap evidence](provider-checks/2026-11-04-representative-4096.json).

### Revised budget decision

- Raise the implemented default output allowance from **2,048 to 4,096 tokens**.
  The old cap demonstrably truncates a modest structured answer. Callers may request
  less; a different model needs its own verified format and limits.
- Revise the planned quick/deep model-attempt ceilings from **10/18 to 8/16**,
  retaining 4/8 query attempts, 4/10 extraction attempts, and 120/240-second hard
  deadlines. Using the slowest successful timings from these two representative
  runs (10.67 s model, 4.27 s search, 0.77 s extraction), the old ceilings imply
  roughly 127/234 seconds of serial provider work; the revised ceilings imply
  roughly 106/213 seconds. These calculations include no extra retry attempts
  outside the ceilings and leave some room for backoff and local work. They are
  planning estimates, not promises that every maximum can be used.
- Set the planned finalization reserve to **three model attempts and 45 seconds**
  within those totals: three observed slow model calls take about 32 seconds.
  A slow provider or repeated failures can still prevent all three from completing.
  The controller must stop research before the reserve and respect the hard deadline.
- Retain the implemented **45-second per-attempt timeout** for now. The measured
  maximum was about 11 seconds, and this small sample cannot establish a safe tail
  cutoff. The shared deadline still clips every attempt and prevents overruns.

The output cap is implemented here. Quick/deep profiles, finalization reserves,
and the shared two-in-flight limit are explicit Step 3 controller work; they are
not enforced by constructing a `CallBudget` alone. Rebenchmark actual research
prompts before treating these revised starting profiles as adequate for the full
pipeline. A valid partial result remains preferable to spending past the deadline.

## Sources checked

- [Nebius deployed API specification](https://api.tokenfactory.nebius.com/openapi.json)
- [Nebius structured-output guide](https://docs.tokenfactory.nebius.com/ai-models-inference/json)
- [Nebius rate-limit behavior](https://docs.tokenfactory.nebius.com/ai-models-inference/rate-limits)
- [Nebius Nemotron pricing](https://nebius.com/services/token-factory/models/nvidia-nemotron-models-inference)
- [Tavily search API](https://docs.tavily.com/documentation/api-reference/endpoint/search)
- [Tavily extraction API](https://docs.tavily.com/documentation/api-reference/endpoint/extract)
