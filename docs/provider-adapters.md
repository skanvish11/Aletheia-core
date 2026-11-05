# Step 2: provider connections

The backend can now make explicit, bounded calls to Nebius for structured model
responses and to Tavily for search and page extraction. Both integrations passed
live checks on November 4, 2026 (America/Los_Angeles).

Claim submission still saves queued investigations. There is no worker or research
pipeline yet: health, submission, and saved reads make no provider calls. Step 3
will connect interpretation, planning, research, and evidence-linked conclusions.

## Implementation

| File | Responsibility |
| --- | --- |
| `src/aletheia/providers/settings.py` | Provider-only settings and secret wrappers. |
| `src/aletheia/providers/common.py` | Safe errors, HTTP lifecycle, retries, deadlines, size limits, and attempt accounting. |
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
| `ALETHEIA_MODEL_MAX_OUTPUT_TOKENS` | `2048` | Model output cap; range 64–16384. A call may request a lower cap. |

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
query-selected chunks. Page text is preserved exactly as returned. Results follow
input URL order, even if the provider reorders them. Failed, empty, and omitted
pages become explicit per-URL outcomes; successful pages remain available.
Unrequested, duplicate, or contradictory URL records invalidate the response.
Search snippets and extracted page text have separate result types.

Every operation requires a `CallBudget` with model, query, and extraction-attempt
ceilings and an absolute `time.monotonic()` deadline. Share the same object across
one investigation; do not recreate it per call. Reservations happen before dispatch
without yielding, so concurrent coroutines on one event loop cannot overspend.
Extraction charges one attempt per requested URL, including failed URLs and retries.
The future controller owns finalization reserves and concurrency policy.

Transient timeouts, network errors, HTTP 429, and selected temporary service errors
can retry. Authentication, invalid requests, quota errors, malformed output, and
refusals do not. Backoff honors `Retry-After` in seconds or HTTP-date form. If the
wait cannot fit, return the provider failure without retrying early. In-flight
requests are cancelled at the shared deadline; cancellation is preserved. Each
attempt records its provider, operation, units, elapsed time, HTTP status if known,
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

Final local verification: 148 tests passed on Python 3.12.14, Ruff lint and format
checks passed, both deliberate faults were detected, and `git diff --check` passed.
Dependencies were synchronized from the lockfile while preserving pre-existing
development tools (`uv sync --locked --dev --inexact`); checks used
`uv run --locked --no-sync` afterward. No remote CI or independent agent review
was run in this task.

The live script makes no calls or dotenv reads without `--live`. Supply your exact
runtime settings file and a verified model. For example, with keys already in the
process environment:

```sh
uv run --locked python scripts/smoke_providers.py --live \
  --model nvidia/Nemotron-3_5-Lightning --samples 2 \
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
are limited to 1–3; the deadline is configurable from 30–300 seconds.

## Acceptance evidence

| Requirement | Evidence |
| --- | --- |
| Correct authenticated requests and strict model output | `tests/test_providers.py`, live structured responses. |
| Search results, metadata, and empty-result semantics | `tests/test_providers.py`, live search. |
| Partial, missing, empty, reordered, and untraceable pages | `tests/test_providers.py`, live successful extraction. |
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

No live transient retries were needed. Retry behavior and accounting were verified
offline; no provider faults were intentionally induced. This small synthetic sample
does not measure research accuracy, long source-heavy prompts, or tail latency.

### Budget decision

Keep the proposed 120/240-second quick/deep deadlines provisional. A 45-second
per-attempt cap leaves headroom above the observed 3–5-second model calls while
the shared deadline prevents retries from overrunning a run. Ten model attempts
at the slowest observed time would consume roughly 48 seconds before other work;
this is an illustrative calculation, not a full-pipeline estimate. Start Step 3
with these measured defaults, then benchmark real interpretation/assessment/synthesis
prompts before changing the quick/deep ceilings or finalization reserve.

## Sources checked

- [Nebius deployed API specification](https://api.tokenfactory.nebius.com/openapi.json)
- [Nebius structured-output guide](https://docs.tokenfactory.nebius.com/ai-models-inference/json)
- [Nebius rate-limit behavior](https://docs.tokenfactory.nebius.com/ai-models-inference/rate-limits)
- [Nebius Nemotron pricing](https://nebius.com/services/token-factory/models/nvidia-nemotron-models-inference)
- [Tavily search API](https://docs.tavily.com/documentation/api-reference/endpoint/search)
- [Tavily extraction API](https://docs.tavily.com/documentation/api-reference/endpoint/extract)
