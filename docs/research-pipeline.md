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
5. `verdicts.py` computes a preliminary True/False decision, or an unable-to-decide
   outcome for insufficient or conflicting evidence. A direct check can use an
   authoritative record. Deep definitive findings require two documented distinct
   origins with distinct content, or a relevant synthesis with explained coverage.
   Unknown independence never counts as established independence. Missing support
   is not contradiction, and unresolved conflict is never Almost.
6. If the evidence does not settle the claim, the controller escalates quick to
   deep once and requests new queries for a named gap. There are at most two
   follow-up rounds. An empty follow-up plan ends normally with the available finding.
7. The model proposes cited explanation units and, only when eligible, an Almost
   correction. Code checks references and evidence sufficiency for each correction
   part. The existing final-check model task verifies the explanation and whether
   the correction is grounded, preserves a substantially true core and leaves no
   unresolved conflict. A failed check publishes no factual verdict. This remains
   a model-assisted semantic check, not a proof of truth. No extra provider calls
   are introduced into the normal synthesis/check sequence.
8. The result and terminal event are committed together. Refresh comparison happens
   after the new finding and explanation; old verdicts never enter research prompts.

All model input is marked untrusted, including user text and extracted pages.
Models cannot execute tools or write storage. Instructions and schemas live with
these task modules and are labeled `one-claim-v2`. Results record the model,
application/prompt versions, allowlisted configuration, call attempts and available
token usage. Token totals include usage from successfully parsed model responses;
providers may not report usage for malformed or failed attempts.

## Bounds and honest outcomes

| Limit | Quick | Deep after routing/escalation |
| --- | ---: | ---: |
| Model attempts, including retries/repairs | 8 | 16 |
| Search attempts, including retries | 4 | 8 |
| Extracted URL attempts, including retries | 4 | 10 |
| Hard provider-call deadline | 120 seconds | 240 seconds |

Escalation keeps the original start time and all accumulated usage. Research leaves
three model attempts and 45 seconds for finalization. Retry timeouts use that same
research deadline, so they cannot silently consume the time reserve. Finalization
may use the reserve, but never start a call after the hard deadline. These remain
provisional defaults; no full-pipeline live latency measurements have been made.

Calls execute sequentially, with at most one in flight. The provider output cap is
4,096 tokens, following Step 2’s representative measurements.

Each search requests at most five results. Extraction retains at most 100,000
characters by default and exposes `page_text_truncated` in saved limitations. If
a configured provider limit exceeds the pipeline’s 100,000-character storage cap,
oversized pages are rejected with an explicit event. Assessment receives at most 120 complete
spans totaling 12,000 characters per source; omitted material is a visible
limitation. An oversized first block is not silently cut into a misleading quote.
A truncated assessment cannot establish comprehensive synthesis coverage.

- `completed`: the research stopped normally, including an honest
  `unable_to_decide` outcome when no useful next search was identified.
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

## Decision contract

The only truth labels are `true`, `false`, and `almost` (JSON strings). `outcome`
is `decided` or `unable_to_decide`. An undecided result has a null verdict and a
reason of `insufficient_evidence` or `conflicting_evidence`. This is independent
of the execution status: completed work may honestly be unable to decide.

Almost always includes `almost_correction` with three cited `{text, evidence_ids}`
parts: `what_is_correct`, `what_needs_correction`, and `corrected_claim`. Each part
must pass the same evidence threshold as a definitive finding for the route. The
corrected claim must differ from the original while retaining its essential subject
and proposition. A missing part, blank text, invented reference, insufficient evidence,
unsupported correction or unresolved conflict cannot produce Almost. False remains
False unless the full correction passes validation. Unknown remains a separate outcome.

The final check independently evaluates five conditions: supported core, supported
correction, supported corrected claim, preservation of the core, and no unresolved
conflict. All must pass. If the deadline prevents that check, the candidate correction
and generated prose are discarded; the previously validated finding is saved as partial.
These are bounded model judgments, not guaranteed semantic truth; live evaluation
is still required. The frontend must use the presentation mapping below; UI
implementation and styling belong to the later frontend integration.

### Frontend presentation and evaluation handoff

Derive the visible result label from the saved decision fields, independently of
execution status. API verdict values are strings, not JSON booleans.

| `outcome` | `verdict` | `unable_to_decide_reason` | Visible result label |
| --- | --- | --- | --- |
| `decided` | `"true"` | `null` | **True** |
| `decided` | `"false"` | `null` | **False** |
| `decided` | `"almost"` | `null` | **Almost**, with the cited correction |
| `unable_to_decide` | `null` | `insufficient_evidence` | **Insufficient evidence** |
| `unable_to_decide` | `null` | `conflicting_evidence` | **Conflicting evidence** |

Keep Almost as its own label; do not rename it Mixed or map unresolved conflict
to Almost. Display its three cited correction parts: what is correct, what needs
correction, and the corrected claim. Insufficient evidence is an explicit visible
result even though it is not a truth verdict. Do not collapse the two undecided
reasons into a generic Unknown label in the result view, saved history, or evaluation.

Show execution status separately: a completed investigation can return either
undecided label, and a partial investigation can retain a validated decision while
showing its incomplete-coverage limitations. A failed investigation with no saved
result must display its failure state, not an inferred Insufficient evidence label.

PR #7's evaluation contract must represent and score these same five valid
outcome/verdict/reason combinations, keeping insufficient and conflicting evidence
distinct. Almost evaluation must also check the three cited correction parts and
their grounding, preservation of the claim's core, and absence of unresolved
conflict; matching the Almost label alone is not sufficient. Execution failures
and partial coverage must be reported separately from decision-label correctness;
PR #7's acceptance scoring still counts partial and failed runs as wrong.
This documents the integration requirement; it does not implement or validate
PR #7's evaluation changes or the frontend rendering.

Example undecided decision fields:

```json
{
  "outcome": "unable_to_decide",
  "verdict": null,
  "unable_to_decide_reason": "conflicting_evidence",
  "almost_correction": null
}
```

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

SQLite schema 3 retains the `research_records` and `idempotency_keys` tables added
in schema 2. Research records contain typed snapshot/span, evidence and comparison
JSON. The exact owned schemas 1 and 2 migrate transactionally; foreign schemas are
rejected. Requests, timestamps, source/evidence records and progress events survive.

For existing schema-2 results, the migration archives the original result JSON
verbatim in `research_records` as `legacy_result/schema-2`. It maps `supported` to
`true`, `contradicted` to `false`, `mixed` to unable-to-decide/conflicting-evidence,
and `insufficient_evidence` to unable-to-decide/insufficient-evidence. It never
infers Almost from an old result. Explanation text and original prompt/application
versions stay unchanged; the old response is retained in the archive. No research
is triggered by migration. Prior comparison JSON is also archived as `legacy_comparison`;
its verdict-change flag is translated separately from its decision-change flag so
conflict versus insufficient-evidence remains distinguishable. Malformed historical
data rolls back the entire migration.
A schema-3 database requires the updated application; old code fails its version guard.

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
versions, plus source limitations (fingerprint algorithm `relevant-evidence-v2`).
They exclude run IDs, retrieval time and model-assigned relation labels.
Only equal nonempty sets and exact assertion text establish equal relevant evidence.
Changed decisions over equal evidence always produce an unresolved inconsistency
flag. Comparison exposes `verdict_changed` separately from `decision_changed`;
the latter also detects a changed undecided reason or changed Almost correction
text. New run-specific evidence IDs alone do not change the decision. Exact text
comparison may flag a harmless rewording; semantic equivalence is not inferred. Automatic rechecks are disabled; the initial new finding remains visible.
Harmless page edits and changed provenance can conservatively count as changed
research evidence even when a displayed quotation is identical.

## Verification and remaining evaluation

The offline suite uses the real Nebius/Tavily HTTP adapters with synthetic responses,
FastAPI lifespans and temporary SQLite files. It covers True/False/Almost and separate undecided
outcomes, ambiguity, plan validation, invented citations, scope and
origin rules, extraction failure, provider-error propagation, retained-prefix limitations,
bounded repairs, deadline/reserve behavior,
refresh races, exact saved reuse, SSE replay/disconnect, interruption and migration.
Transaction tests inject SQLite failures after earlier writes and verify rollback.
The sensitivity script deliberately breaks citation, terminal-transaction, budget-reserve
and Almost-validation protections in temporary copies.

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

Local verification after the verdict update: **244 tests passed** on Python 3.12; Ruff lint,
format and whitespace checks passed. All four deliberate protection faults were
detected. The localhost walkthrough passed submission/reuse and a fresh-process
restart with identical saved records. No independent agent review or live research
quality evaluation was performed. GitHub Actions results are separate from these
local observations.
