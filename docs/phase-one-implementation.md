# Phase one implementation: direct records and comparisons

This implements the first code milestone in [the agreed plan](direct-claims-phase-one.md).
It does not establish the proposed acceptance scores. The 1,000-claim dataset, independent
label review, frozen evaluation settings, and live end-to-end evaluation remain pending.
No historical pilot claims, labels, saved outcomes, or archived runtime files are changed.

## Behavior

Every new research run parses the original assertion into a versioned `direct-v1`
analysis: claim type, scope completeness, required method, support decision, reason,
and up to eight material components. Components retain exact substrings, roles,
subjects, predicates, dates, locations/populations, and comparison specifications.
Python rejects invented component text, rewritten assertions, and dropped numeric
modifiers. It cannot prove semantic parsing completeness; that requires evaluation.

Direct facts and compatible comparisons enter research. Causal, predictive,
counterfactual, scientific-inference, interpretive and mixed-method claims receive an
explicit unsupported-method response when their scope is clear. Missing essential
scope remains a separate clarification response. An adverse routing decision gets
one bounded review; changed method/scope decisions produce a `route_revised` event
with the previous classification and the revision reason. This review uses the same
configured model and is not an independent correctness guarantee.

Passage selection ranks spans across the saved document using claim terms and document
frequency, removes recognizable navigation/link-only boilerplate, and adds adjacent
context within 12,000 characters and 120 spans. Saved offsets, IDs and quote text remain
unchanged. This is a lexical selector, not a proven semantic retrieval algorithm.

Assessments cite individual components. A different date for the same event is a
contradiction; a different entity or population is a scope mismatch. True requires
adequate support for every component. A contradicted essential proposition can yield
False; a contradicted modifier cannot be swallowed by support for the main proposition.
A supported bounded correction can yield Almost after reference and semantic checks.
Conflicts are evaluated within components, rather than confusing support for one part
and contradiction of another with disagreement between sources.

For new direct claims, a relevant authoritative record has the same sufficiency rule
under quick and deep effort. Truncation limits comprehensive-synthesis claims but does
not automatically invalidate a narrow original record. The legacy decision helper
retains its historical behavior for assertions lacking `analysis`; new runtime
interpretations always supply it.

Comparisons extract exact values, entities, metrics, units, periods, populations,
definitions and uncertainty. Literal extraction text must occur in cited spans;
numeric tokens (including signed values and comma-separated thousands) and ISO dates
must occur in that extraction text. Python compares finite
Decimal values, ISO dates, or equality/inequality of recorded properties. Operands
may come from different documents, but each needs adequate evidence. Incompatible,
uncertain or ungrounded operands cannot support a comparison verdict. Units must be
explicitly compatible; automatic unit conversion and non-ISO date normalization are
not implemented. A grounded counterexample can refute a superlative; a single pair
cannot prove exhaustive coverage of its comparison set.

Search plans must fit remaining search capacity before execution. If a later search
attempt fails after an earlier search succeeds, gathering retains the successful
results for extraction where budget permits. Invalid source assessments receive the
existing one-repair limit, then are isolated; valid earlier evidence remains saved.
Incomplete coverage produces a partial outcome rather than a completed investigation.

Final checking covers both cited prose and the full component decision. One bounded
semantic repair can regenerate the explanation or propose a justified correction.
A provisional True can be revised when relevant correction evidence is present.
Failed checks and deadlines never publish an unchecked truth verdict. Source/evidence
records survive finalization failure. All additional work uses the existing shared
call/deadline budgets and finalization reserve; no hidden retry allowance is added.

## API and persistence compatibility

`GET` and `POST /investigations` add nullable `claim_analysis` and `method_limitation`.
Existing requests and factual outcome labels are unchanged. New research results add
`assertion.analysis`, `finding.components`, and evidence assessment fields
`component_id` and `values`. Historical saved records read with null/empty defaults;
they are not reclassified or rescored during retrieval.

A clear unsupported claim terminates as:

```json
{
  "status": "completed",
  "stop_reason": "unsupported_method",
  "result": null,
  "clarification_questions": null,
  "claim_analysis": {"required_method": "scientific_inference", "supported": false},
  "method_limitation": {
    "outcome": "unsupported_method",
    "original_claim": "The original submitted wording",
    "analysis": {"required_method": "scientific_inference", "supported": false},
    "explanation": "This investigation method is outside phase one."
  }
}
```

The example abbreviates the analysis fields; use generated OpenAPI for the full schema.
Here `completed` describes execution of routing, not completion of factual research.
Clients must inspect `method_limitation`, not assume every completed response has a
factual result. Unsupported responses are excluded from factual decision scoring.
They support exact saved reuse and explicit idempotent refresh without modifying the
old version. Existing UI clients need to render the new method-limitation field.

New stop reasons distinguish `invalid_task_output` and `semantic_rejection` from
`provider_failure`. New progress events are `route_revised`, `assessment_rejected`,
and `search_incomplete`.

SQLite remains schema version 3: this is an additive versioned record contract, with
no table/column migration. Analysis and unsupported responses use the existing
append-only `research_records` table. Unsupported response insertion, terminal status
and terminal event commit atomically. The existing version-1/version-2 migrations
remain covered. Older application versions do not understand these new response
contracts; use the current application to read databases containing phase-one runs.

Final-check diagnostic artifacts are separate from public records, under
`<database filename>.diagnostics/` next to the configured database. The directory is
owner-only (0700) and each new file owner-only (0600). A permissive or symlinked
directory is refused. Artifacts contain failed conditions, affected unit/component
IDs, evidence references, structured check results and only the rejected bounded
user-facing explanation. They contain no raw provider response or private reasoning.
They are not served by API/SSE and are ignored by Git. A diagnostic write failure
cannot replace the research result, original failure or cancellation. Operators
should retain these local artifacts only as needed for debugging.

## Validation and limits

`tests/test_phase_one.py` covers the six diagnosed failures using saved pilot text
and controlled responses, plus route revision, comparison grounding, incompatible
operands, failed-decision checks, diagnostic failure, atomic unsupported completion,
restart and refresh. Existing tests that depended on the old deep-only evidence bar
now explicitly use non-authoritative evidence when testing follow-up capacity.
Deadline tests require no published unchecked verdict. Historical pilot files remain
unchanged and are not used as unseen evaluation cases.

Local validation uses the existing development environment because `uv` is unavailable
on this host. The offline suite blocks external network calls and dotenv access.
Local results (Python 3.15.2):

| Check | Observed result |
| --- | --- |
| `PYTHONPATH=src pytest -q` | 411 passed, 1 existing expected failure |
| `ruff check .` / `ruff format --check .` | Passed; 128 Python files formatted |
| `scripts/check_research_test_sensitivity.py` | All 18 deliberate faults detected |
| `scripts/smoke_foundation.py` | Local HTTP submission/reuse and process restart passed |
| Small `scripts/benchmark_foundation.py` correctness run | Passed with 10 saved records |
| `scripts/inspect_pilot_handoff.py` | 110 historical files verified, original results unchanged |
| `git diff --check` | Passed |

The suite includes 40 new Phase 1 checks. Remote CI separately runs Python 3.12 and
3.13 and local-server checks on Linux and Windows; local results do not establish its
outcome.
The fault checks include missing-component True decisions and reversed comparison
arithmetic, alongside existing citation, transaction, budgeting and diagnostic guards.

One adversarial expected failure remains: a model can label an unrelated passage as
support and its checker can agree. Structural validation and repeat model checks do
not establish factual accuracy. Routing, semantic component extraction, authority
judgments, property equivalence, and citation meaning need the planned independently
reviewed evaluation. This PR is an implementation milestone, not phase-one acceptance
or permission to begin causal/predictive research.
