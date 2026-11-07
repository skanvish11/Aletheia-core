# Adversarial review: failure coverage and traceability

Reviewed November 5, 2026 (Pacific time), against PR #18. This is a code review with executed adversarial synthetic cases, not an independent human review of the factual claims. No new paid provider calls were made for this review.

**The PR does not fix all the causes of the failed evaluation.** It improves execution controls and now makes future failures substantially more traceable. Two adversarial cases still demonstrate incorrect behavior. Eleven original baseline failures have no preserved specific provider error code, so their exact causes cannot be reconstructed from new instrumentation.

## Findings, ordered by impact

### P1 — Valid references can still accompany an unsupported verdict (open)

`evidence.admit` verifies snapshot/span identity and structural consistency. The verdict policy then trusts semantic fields such as `relation`, `scope_match` and `authoritative_record`. If the assessment and explanation checker agree on an unsupported interpretation, a structurally valid True result can still be published.

**Reproduction:** a synthetic page says only that an archive's gift shop sells postcards. The model labels that passage authoritative support for an opening-year claim and its explanation checker agrees. The pipeline completes with True. This reproduces the distinction exposed by Apollo's weak exact-span support, without asserting that this synthetic text appeared in the live run.

**Status:** not fixed. `test_references_alone_cannot_make_unrelated_passages_support_a_claim` is an explicit strict expected failure. It is not counted as a passing protection. Exact-span entailment, source-origin checks and human citation review remain priorities. A matching verdict or valid citation ID is not an accuracy measure.

### P1 — Clarification protection trusts the model's reason label (open)

The existing guard rejects `factual_uncertainty`, but accepts `missing_scope`. A model can ask the same truth question while assigning the latter label.

**Reproduction:** “Did the Archive open in 2000?” with `clarification_reason=missing_scope` is accepted as a clarification request for the already explicit claim. The original guard does not stop this path.

**Status:** not fixed. `test_truth_question_cannot_bypass_guard_by_claiming_missing_scope` is a strict expected failure. A stronger contract must identify the actual missing scope and validate what the user has already supplied; recovery must be evaluated separately from rejecting a bad question. Legitimate ambiguity must still be preserved.

### P2 — Quick research has little repair capacity (open)

The quick profile permits eight total model attempts, reserving four for finalization. Interpretation, planning and two assessments already consume the four research attempts. A repair can use up the remaining research capacity before the evidence gate can escalate the run to deep research. This explains why an assessment repair in the Curie follow-up could not start; it is distinct from a wall-clock timeout.

**Status:** budgets were not increased or the reserve weakened. The trace now records used/total/available model limits, phase, remaining time and the specific `model_finalization_reserve` stop. A subsequent behavior change should explicitly address repair allocation or escalation, then verify preserved finalization capacity.

### P2 — Search/extraction failures were missing durable attempt diagnostics (fixed here)

The original PR emitted model diagnostics only after the model task returned. Search/extraction errors could lose HTTP status, duration and attempts when no result was saved. A first transient failure also remained invisible while the next model attempt was running. Extraction could retain the preceding stage until extraction finished.

**Change:** provider start/finish/retry/rejection events are persisted at the shared HTTP boundary for both providers, on every attempt. Stage is set before extraction. Configuration is persisted before research. Tests inject search 503/504 and extraction 403 responses, inspect the trace during a held-open retry, and verify saved replay after restart.

### P2 — Schema failures discarded useful metadata (fixed here)

A complete HTTP-200 response with invalid JSON or an invalid task schema previously collapsed into generic `invalid_response`; validated finish reason and usage could disappear. This obscured whether a response was cut off, malformed, or rejected by a specific task contract.

**Change:** model diagnostics distinguish envelope, shape, JSON and schema errors. They retain available usage, output-character count, finish reason, bounded trusted top-level field names and allowlisted error types. Optional provider-reported reasoning-token counts are retained only when valid; absent counts remain unknown. Unknown extra keys, input values, private reasoning, exception text and response bodies are never diagnostic output. A deliberate mutation that permits untrusted extra-key names is detected by the privacy test.

### P2 — Attempts could not be tied reliably to the failing page/task (fixed here)

Repeated `assess` tasks used the same task name without a unique invocation or snapshot reference. Failed runs also lacked configuration and budget context. Internal exceptions could look like provider failures, including a misleading cancelled-attempt outcome.

**Change:** task invocation IDs, provider call IDs, retry numbers, query IDs, selected-candidate IDs and snapshot IDs connect the stages. Selection events state the actual selection rule. Each task includes budget state; unexpected internal exceptions get a safe `internal_error` trace. Public terminal error wording remains generic. Tests ensure context from one page does not leak into synthesis and that internal exception text remains private.

## Before → change → current evidence

| Observed failure | Why it failed / what is known | Implemented change | Still open |
| --- | --- | --- | --- |
| t001–t004, t006–t012: 11 baseline evidence-checking failures | Each saved one source and no assessment; exact internal cause absent. Separate Apollo probes confirmed truncation. | Smaller task responses; opt-in direct-output mode; durable task/provider metadata. | Cannot retroactively attribute all 11 to truncation. Default thinking still truncated the post-change pilot. |
| Apollo diagnostic/trial cut-offs | Responses reached the output-token cap, including an 8,192-token exploratory trial. | Explicit Nemotron thinking control, bounded generated text, preserved usage/finish reason and optional reasoning-token count. | Latest direct-output Apollo completed, but this is a small probe with citation concerns, not proof of repeatability or accuracy. |
| t014/t015: interpretation deadline; t013/t018: partial results after deadlines | Research stopped before enough useful evidence or a checked explanation was available. | Start/finish timings, timeout status, retry decisions, current/hard remaining time, distinct deadline/reserve reasons. | No latency fix or new stage allocation has been validated. Partial results remain unsuccessful in scoring. |
| t005/t016/t017/t019/t020: clarification instead of research | Questions asked for factual answers; Almost boundaries also need human scope review. | Explicit reason contract, rejection/one repair for declared factual uncertainty; record accepted clarification reason. | Einstein still fails recovery, and the adversarial missing-scope relabeling bypass remains open. |
| Curie follow-up: citation repair could not start | Invalid citation spans, then the research model allowance was exhausted. | Specific citation repair guidance, source/task correlation, explicit reserve-stop metadata. | Repair allocation/escalation remains unchanged. Do not confuse a call allowance with a timeout. |
| Follow-up explanation-index rejections | Checker expected zero-based positions without explicit indices in input. | Explicit indexed units and matching instructions; targeted repair and final semantic-rejection codes. | Fixing index validity does not establish semantic correctness. |
| Navigation/secondary sources and weak exact-span support | Retrieval and model assessment did not reliably establish the scoped fact. Apollo's completion exposed this again. | Selected sources now trace to queries, extraction and assessment; existing passages/assessments remain inspectable. | Source selection, provenance, entailment and final checking remain unsolved quality work. |
| All 20 expected labels unreviewed; no validated demo | Proposed expectations are not ground truth; saved/replay checks can pass for failed research. | Reports preserve proposed status, all failures, separate execution/quality measures and the original baseline. | Human labels/citation review, held-out evaluation, successful refresh and browser demo remain outstanding. |

For exact wording, context, proposed answers and every baseline outcome, use the [20-claim worksheet](review-and-fix-plan.md). The [seven follow-up attempts](repairs.md) and [portable observations](repair-observations.json) remain unchanged by this review.

## What the trace now answers

- **Which run and configuration?** Investigation/version IDs are on the saved record and event envelope. `run_configured` preserves model, application/prompt versions, response format, thinking mode, output cap, timeout/retry settings, byte limits and reserves even when no result is produced.
- **Which step, call and source?** `task_started`/`task_finished` carry a task invocation ID. Provider events carry a provider call ID and attempt number. Query → selected candidate → extraction → snapshot → assessment links are explicit. Source-selection rules explain the mechanical choice; they do not certify relevance.
- **Did an HTTP attempt happen, fail or retry?** `provider_attempt_started`/`provider_attempt_finished` preserve operation, status, request/response sizes and elapsed time. Retry events record the delay or why retries stopped. A call rejected by budget gets a separate event and makes no network call.
- **Was the response truncated, malformed or invalid?** Task events distinguish `truncated_output`, `response_json`, `response_schema`, known citation errors, factual uncertainty and final semantic rejection. Available token counts, output size and finish reason are retained. Missing provider usage is unknown, never zero by assumption.
- **Which limit stopped progress?** Events record phase, used/total/available attempt limits, current and hard remaining time, and reasons such as `model_finalization_reserve`, `research_deadline` or `hard_deadline`.
- **Can we inspect it after failure or restart?** The ordered events are persisted in SQLite and replay through the existing events API. No new research is launched by reading them. The evaluation runner already exports these events into each case artifact.

New runs emit one `provider_attempt_finished` event per attempt and retain task usage and validation metadata in `task_finished`. Historical `model_attempt_finished` events remain readable, but are no longer emitted. **Do not add historical model events to the provider-attempt count** or calls will be double-counted. Provider attempt records represent local reserved attempts; a crash/deadline may occur before delivery, and they are not billing receipts. The live evaluation's transport counter is a separate network-attempt measure.

## Concrete example

The committed [trace example](trace-example.json) comes from an executed **offline synthetic search-503 failure**, not one of the historical live cases:

1. Configuration saved; interpretation and planning succeed.
2. A query ID links to the Tavily search call.
3. Search returns HTTP 503 with `outcome=unavailable` and `stage=searching`.
4. Retry stops because this synthetic profile allows no retries.
5. `research_stopped` shows two model attempts used, one search used, and substantial time still available; the run ends failed with no factual result.

This distinguishes a search service error from model truncation, invalid citations and budget exhaustion without reading a provider response body.

For a real saved investigation, fetch `GET /investigations/{id}/events` (or its `links.events` URL). The SSE stream carries ordered JSON event data and supports replay with `Last-Event-ID`. For a retained evaluation case, open its JSON artifact's `events` array. Use the last rejected/stopped/failed event, then follow its call/source identifiers back through the trace.

## Limits and validation

Instrumentation cannot recover metadata that old runs never saved, determine why a provider is slow internally, prove that an accepted passage supports a claim, or supply missing human ground truth. If storage is unavailable or the process is killed, the trace may end at a started call; interruption recovery is evidence of interruption, not a fabricated completion. No private reasoning or raw provider responses are stored to fill these gaps.

The two strict expected failures are documented open defects; they are reported separately from passing tests and turn into unexpected-pass failures when behavior changes, forcing review. Only the intended assertion failures qualify; other exception types are not hidden. The new instrumentation tests cover redaction, failed-run/restart replay, retries visible while in flight, budget rejections without network access, source correlation and internal error classification. Trace writes consume time too: tests verify they cannot cause a new HTTP call or retry sleep after the applicable deadline. Known interpretation, planning and correction contract errors now have fixed codes and safe repair guidance rather than generic task rejection.

Local results: **338 passed, 2 explicit expected failures**; Ruff lint/format and `git diff --check` passed. **14/14 deliberate faults were detected**, including disabling durable provider tracing and exposing untrusted schema keys. Python 3.15.2 was used locally. No new live-provider, browser, held-out or human-label evaluation was performed. Remote CI status is separate in the PR checks.
