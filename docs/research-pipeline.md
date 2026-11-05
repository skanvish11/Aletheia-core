# Step 3: one-claim research pipeline

This branch is stacked on Step 2 (`feat/provider-adapters`, PR #10). It implements
one scoped assertion per investigation, with the basic progress, refresh and saved
comparison behavior agreed for V1. Compound claims ask for clarification instead
of silently checking only part of the input. No frontend changes are included.

## Enable research deliberately

The default remains `ALETHEIA_RESEARCH_ENABLED=false`: the API works without
credentials and leaves new investigations queued. Set it to `true` to start the
single background worker. Starting an enabled server also consumes existing queued
work. Reads, health checks and exact resubmissions of terminal requests never call
providers. There is no public hosting or multi-process worker support.

```sh
uv sync --locked --dev
ALETHEIA_RESEARCH_ENABLED=true uv run --locked aletheia
```

Configure `NEBIUS_API_KEY`, `TAVILY_API_KEY` and an explicit `NEBIUS_MODEL` through
the runtime environment. Existing Step 2 provider settings still apply. Runtime
may load the working directory's dotenv file; never inspect, copy, print or commit
its contents. Missing provider configuration fails enabled startup with a safe
message. A disabled server still exposes saved results, evidence and comparisons.

## What executes

1. `claims.py` asks the model to scope one assertion, detect ambiguity and recommend
   research depth. Python overrides quick to deep for consequential or non-direct
   claims. Predictions and value judgments require a checkable reformulation.
2. `planning.py` requires an initial support search and counterevidence search.
   Every query must reference `a1`; duplicate and previously used queries are
   rejected after case/whitespace normalization. One task repair is permitted.
3. `research.py` executes approved queries, alternates their ranked results when
   selecting pages, and extracts through Tavily. Search snippets never become
   evidence. It saves the original text and immutable snapshot before assessment.
4. `verification.py` supplies bounded numbered spans to the model. Python validates
   snapshot and span references, reconstructs exact excerpts, and rejects invented,
   unsupplied, repeated or reversed references. Non-adjacent quotations stay separate.
5. `verdicts.py` computes the four possible verdicts. A direct check can use an
   authoritative record. Deep definitive findings require two documented distinct
   origins with distinct content, or a relevant synthesis with explained coverage.
   Unknown independence never counts as established independence. Material support
   and contradiction produce `mixed`; missing support is not contradiction.
6. If the evidence does not settle the claim, the controller escalates quick to
   deep once and requests new queries for a named gap. There are at most two
   follow-up rounds. An empty follow-up plan ends normally with the available finding.
7. The model proposes cited explanation units. Code checks their evidence IDs;
   another bounded model task checks whether each unit is grounded in its cited
   passages. A failed final check publishes no factual verdict. This remains a
   model-assisted semantic check, not a proof of truth.
8. The result and terminal event are committed together. Refresh comparison happens
   after the new finding and explanation; old verdicts never enter research prompts.

All model input is marked untrusted, including user text and extracted pages.
Models cannot execute tools or write storage. Instructions and schemas live with
these task modules and are labeled `one-claim-v1`. Results record the model,
application/prompt versions, allowlisted configuration, call attempts and available
token usage. Token totals include usage from successfully parsed model responses;
providers may not report usage for malformed or failed attempts.

## Bounds and honest outcomes

| Limit | Quick | Deep after routing/escalation |
| --- | ---: | ---: |
| Model attempts, including retries/repairs | 10 | 18 |
| Search attempts, including retries | 4 | 8 |
| Extracted URL attempts, including retries | 4 | 10 |
| Hard provider-call deadline | 120 seconds | 240 seconds |

Escalation keeps the original start time and all accumulated usage. Research leaves
three model attempts and 20 seconds for finalization. Retry timeouts use that same
research deadline, so they cannot silently consume the time reserve. Finalization
may use the reserve, but never start a call after the hard deadline. These remain
provisional defaults; no full-pipeline live latency measurements have been made.

Each search requests at most five results. Selected pages over 100,000 characters
are rejected with an explicit event. Assessment receives at most 120 complete
spans totaling 12,000 characters per source; omitted material is a visible
limitation. An oversized first block is not silently cut into a misleading quote.
A truncated assessment cannot establish comprehensive synthesis coverage.

- `completed`: the research stopped normally, including an honest
  `insufficient_evidence` answer when no useful next search was identified.
- `partial`: a time/call/follow-up limit stopped the investigation. Validated
  findings remain available, with incomplete coverage disclosed. If finalization
  runs out of capacity, unchecked generated prose is discarded.
- `needs_clarification`: there is no usable single assertion; questions are saved.
- `failed`: interpretation could not finish, provider/authentication failed,
  repeated task output was invalid, the final explanation was ungrounded, or work
  was interrupted. No final factual result is published.

Narrower evidence cannot count as direct support for a broader assertion. Relevant
context can retain qualification flags even when it does not match the entire
scope. Invalid flags are dropped with an audit event. Source-quality and scope
judgments are still model-generated and can be wrong.

## API and persistence

| Endpoint | Behavior |
| --- | --- |
| `POST /investigations` | Save/reuse exact requests, return promptly; worker consumes new queued work when enabled. |
| `GET /investigations/{id}` | Saved status and typed result, clarification or safe error. Links advertise applicable resources. |
| `GET /investigations/{id}/evidence` | Source metadata, assessment outcomes and reconstructed excerpts; raw page bodies omitted. |
| `GET /investigations/{id}/events` | Persisted SSE replay/live progress; `Last-Event-ID` takes precedence over `after`. Terminal streams close. |
| `POST /investigations/{id}/refresh` | Empty body or `{}`, required `Idempotency-Key`; new version from completed/partial results only. |
| `GET /investigations/{id}/comparison` | Saved comparison or explicit pending/not-applicable/unavailable status; never triggers work. |
| `GET /health` | Database and worker availability; never probes providers. |

Refresh keys are unique across refresh actions. Reusing a key for the same parent
returns the same run, even after completion; using it for a different parent returns
409. Unsupported bodies return 422. Different keys intentionally request different
versions. Allocation, capacity check, key reservation and the queued event share
one transaction. Original results and snapshots are never modified by refresh.

SQLite schema 2 adds append-only `research_records` and `idempotency_keys` tables.
Research records store typed snapshot/span, evidence and comparison JSON, rather
than adding a relational table for each artifact in this initial single-user build.
Only the exact owned schema 1 can migrate; the migration is transactional. Original
requests/events survive. A schema-2 database must not be opened with Step 2 code.

The worker claims one queued row transactionally, makes provider calls outside DB
transactions, and stops claiming new work on shutdown. It allows five seconds for
current work, then cancels and records interruption. Startup recovery handles hard
crashes without automatically retrying partially executed research. A storage
failure stops the worker and makes health unavailable; startup recovery handles
any remaining running record. Disconnecting an SSE client does not cancel research.

## Refresh comparisons

Refresh attempts up to two previous source URLs within the page budget and runs
new support/counterevidence searches. Pages not selected and pages that could not
be retrieved are distinguished; neither is labeled deleted. Content hashes and
publication/title changes are exposed separately.

Relevant-evidence fingerprints include all admitted supporting, contradicting and
contextual passages, their source URL, full normalized content hash, individual
quotation hashes, publication date, publisher, origin and normalization/splitter
versions. They exclude run IDs, retrieval time and model-assigned relation labels.
Only equal nonempty sets and exact assertion text establish equal relevant evidence.
Changed verdicts over equal evidence always produce an unresolved inconsistency
flag. Automatic rechecks are disabled; the initial new finding remains visible.
Harmless page edits and changed provenance can conservatively count as changed
research evidence even when a displayed quotation is identical.

## Verification and remaining evaluation

The offline suite uses the real Nebius/Tavily HTTP adapters with synthetic responses,
FastAPI lifespans and temporary SQLite files. It covers supported/contradicted/mixed/
insufficient outcomes, ambiguity, plan validation, invented citations, scope and
origin rules, extraction failure, bounded repairs, deadline/reserve behavior,
refresh races, exact saved reuse, SSE replay/disconnect, interruption and migration.
Transaction tests inject SQLite failures after earlier writes and verify rollback.
The sensitivity script deliberately breaks critical protections in temporary copies.

```sh
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest
uv run --locked python scripts/check_research_test_sensitivity.py
uv run --locked python scripts/smoke_foundation.py
```

A separate opt-in script exercises a live claim through both providers and exports
public result/evidence objects for passage review. It requires explicit authorization
for paid calls and does not run in tests or CI:

```sh
uv run --locked python scripts/smoke_research.py --live \
  --claim 'A precise factual claim to investigate' \
  --output /tmp/aletheia-live-research.json
```

The script can load a runtime settings file with `--dotenv PATH`; it never prints
credentials or raw provider bodies. It deliberately does not label citations
human-reviewed. Inspect the exported passages against the sources before accepting
research quality. Its temporary database is removed after export.

No live Step 3 call or human-reviewed acceptance evaluation was run while building
this PR. The separate evaluation-format PR (#7) explicitly contains no labeled
claim set yet. This PR starts executable synthetic acceptance coverage; it does
not invent human labels, use a held-out set for tuning, or claim research accuracy.
Real-claim passage review, representative latency checks and the reviewed acceptance
set remain release/demo gates. Advanced origin detection, compound assertions,
automatic consistency rechecks and frontend integration remain outside this V1.

Local verification for this PR: **197 tests passed** on Python 3.12; Ruff lint,
format and whitespace checks passed. All three deliberate protection faults were
detected. The localhost walkthrough passed submission/reuse and a fresh-process
restart with identical saved records. No independent agent review or live research
quality evaluation was performed. GitHub Actions results are separate from these
local observations.
