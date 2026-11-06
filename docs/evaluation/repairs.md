# First evaluation repairs and follow-up observations

This PR begins the repair plan; it does not close Step 7. The original [20-case baseline](results.md) remains **13 failed, 2 partial, 5 clarification requests, 0 completed**. The [review worksheet](review-and-fix-plan.md) lists every claim, observed outcome, issue and proposed next step. All expected labels remain proposals awaiting independent human review.

## Implemented changes

1. **Durable model diagnostics (F01/F03).** Model HTTP attempts and task outcomes now enter the persisted event stream before termination, including failures with no result. Records contain task/schema, duration, status, safe outcome, available token counts and finish reason. Missing usage remains `unknown`. Truncated completions retain validated usage metadata. Known citation/semantic failures have fixed rejection codes; prompts, raw responses, reasoning text and exception messages are never copied into diagnostics. Existing provider failure responses remain generic.
2. **Smaller generation contracts (F02).** Assessment responses allow at most three assessments, six span references per citation, three limitations and three flags. Rationales and generated explanation units are limited to 300 characters; explanations contain at most three units. These are model-generation limits, separate from persisted record schemas, so older saved results remain readable. Prompts require preserving material support and contradiction. Citation, sufficiency and semantic checks remain enforced.
3. **Explicit Nemotron thinking control (F02/F03).** `ALETHEIA_NEBIUS_THINKING=disabled` requests direct output for the exact `nvidia/Nemotron-3_5-Lightning` model. The default remains `default`, sending no control. `enabled` is also explicit; non-default controls for other models fail before network access. Evaluation manifests, successful result configuration and provider smoke reports retain the selection. No model fallback, token-cap increase, deadline increase or extra repair allowance was introduced.
4. **Clarification guard (F04).** Interpretation distinguishes missing scope, compound/non-factual input and factual uncertainty. A response identifying factual uncertainty is rejected and receives one targeted repair; it cannot become a question asking the user to supply the answer. Genuine ambiguity still requests clarification. This does not guarantee the model will classify every question correctly or recover after repair.
5. **Explanation indices and targeted repairs.** Explanation-check inputs now include explicit zero-based indices; instructions and validation agree on those indices. Known invalid citations receive specific fixed repair guidance instead of only “try again.” A generated invalid ID is never echoed into the repair prompt. The same one-repair limit and original budgets apply. Rejected final explanations/corrections now record a safe reason before failure.

Nebius's [model migration verification](https://github.com/nebius/nebius-physical-ai/blob/main/docs/workbench/token-factory-deprecation-verification.md) reports Lightning consuming its output allowance on reasoning and documents `chat_template_kwargs.enable_thinking=false`. NVIDIA's [model card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16) also describes this control. Our initial failure's exact reasoning-token share was not recorded; attributing that failure specifically to reasoning remains an inference. The live observations below establish behavior under the explicit setting, not universal compliance or accuracy.

## Every follow-up attempt

Same model and **4,096-token cap**, 45-second per-attempt timeout, original run budgets, fresh databases, original claim/context, no expected-label or reference-source input. Three sequential variants were run, retaining every attempted case. All manifests identify the checkout as modified; these are development probes, not a clean-release benchmark. The final semantic-rejection audit event was added after these probes and validated offline.

| Variant | Claim | Status | Time | Network attempts | Observation |
| --- | --- | --- | ---: | ---: | --- |
| Compact contracts; default thinking | t001 Apollo | failed | 32.512 s | 7 | Assessment stopped with `length` / `truncated_output`, consuming all 4,096 completion tokens. Compact limits alone did not fix it. |
| Thinking disabled | t001 Apollo | failed | 18.804 s | 8 | Assessment returned complete JSON (665 then 600 output tokens); both attempts failed task validation. Exact rejection codes were not yet captured. |
| Thinking disabled | t002 Curie | failed | 16.701 s | 12 | Interpretation needed repair; research hit the model-call reserve; explanation indices failed validation twice. No result was published. |
| Thinking disabled | t005 Einstein | failed | 54.662 s | 26 | Reached research and synthesis, but no accepted final result. This version lacked a separate final semantic-rejection reason event. |
| Explicit indices and targeted repairs; thinking disabled | t001 Apollo | **completed, True** | 18.717 s | 11 | Returned three cited explanation units. Citation quality concerns remain below. |
| Explicit indices and targeted repairs; thinking disabled | t002 Curie | failed | 20.381 s | 11 | An assessment referenced invalid/unsupplied/unsorted spans (`citation_spans`); its repair could not start because the research call allowance was exhausted. Final output was not accepted. |
| Explicit indices and targeted repairs; thinking disabled | t005 Einstein | failed | 1.793 s | 2 | Both interpretation attempts classified the issue as factual uncertainty. The guard failed safely instead of asking the user to determine truth. No research occurred. |

Total: **7 development probes, 77 network attempts, 1 completed and 6 failed**. Latest three-case probe: **1 completed, 2 failed**. No refresh was run in these probes; billed cost is unknown. These small, sequential, non-controlled runs cannot isolate each change's causal effect or establish an accuracy rate. They do not replace the 20-case baseline or justify calling the original failures resolved.

The portable [observation export](repair-observations.json) includes all seven cases, task diagnostics, saved-read checks, manifests and hashes of the local full artifacts. Full source snapshots and databases remain in the ignored `data/` directories named there. No private model responses are exported.

## Inspecting the completed Apollo result

Agent inspection found that completion is not enough:

- The assessment accepted an [American Philosophical Society transcript page](https://www.amphilsoc.org/item-detail/transcript-first-moon-landing) as an authoritative record, but the selected spans were a dated heading and introductory text about the astronauts and moonwalk. They do not explicitly establish the requested UTC lunar-module touchdown date.
- Another selected source was a social-media AI answer. Some of its admitted support was general discussion of evidence and conspiracy claims, rather than direct support for the precise date.
- The final explanation blended landing and first-walk details and repeated the same source. The automatic explanation checker accepted it. This is a concrete concern for source relevance, scope matching and semantic checking, even though the returned True label matches the proposal.

This is an **agent-reviewed quality concern**, not completed human citation adjudication. Do not present the run as a verified correct answer or a successful research-quality acceptance test. The next repair should inspect exact-span support and source selection before scaling to the full set.

## Remaining work and order

| Issue | Current status | Next check |
| --- | --- | --- |
| F01 diagnostics | Model/task diagnostics and known rejection codes implemented | Verify new final rejection events in the next necessary live run; improve safe schema-failure categorization if needed. |
| F02 truncation | Compact limits alone failed; direct-output probes progressed past truncation | Repeatability and quality across more reviewed claims remain unmeasured. Do not silently change the default. |
| F03 latency/budgets | Stage durations visible; no budgets enlarged | Curie shows a repair can exhaust research capacity. Measure stage allocation before adjusting limits. |
| F04 clarification | Invalid uncertainty requests rejected; recovery unreliable | Einstein remains a failed execution. Improve interpretation without forcing truly ambiguous claims through research. |
| F05 sources/passages | Not fixed | Prioritize exact-claim evidence and original records; reject irrelevant support even from credible publishers. |
| F06 verdict/citation quality | Still unmeasured by humans | Audit Apollo's spans and explanation, then repeat a small reviewed set. |
| F07 labels/coverage | All labels remain proposed | Obtain independent labels, resolve Almost/conflict cases, broaden flag coverage. |
| F08 successful demo | One completed response, with quality concerns | A validated normal/insufficient result, successful refresh and browser walkthrough remain open. |

## Running the explicit profile

From a configured shell, using a new output directory each time:

```sh
ALETHEIA_NEBIUS_THINKING=disabled uv run --locked python scripts/evaluate_research.py \
  --cases docs/evaluation/proposed-claims.json \
  --model nvidia/Nemotron-3_5-Lightning \
  --live --limit 1 --output data/evaluation-direct-pilot
```

This makes paid calls. Leave the setting unset to preserve provider-default thinking. Broader reruns should follow source-quality and interpretation work; no further paid batch is needed merely to publish this PR.

## Validation

Offline regression coverage uses real API lifespans and SQLite with synthetic HTTP providers. It checks durable failed-run diagnostics and restart/replay, secret redaction, bounded repairs, legitimate ambiguity, explicit model-specific controls, old record compatibility, preserved citation checks, zero-based explanation inputs and final semantic rejection. Local Python is 3.15.2; remote CI provides Python 3.12/3.13 checks.

- `uv run --locked pytest -q`: **323 passed**.
- Ruff lint and format checks, plus `git diff --check`: passed.
- `scripts/check_research_test_sensitivity.py`: **12/12 deliberate faults detected**.
- `evals/validate.py`: passed; separate labeling-validator suite: **39 passed**.
- Offline proposal validation: **20 proposed cases accepted**, without provider calls.
- Localhost foundation restart smoke passed while preparing the baseline package; the repair regressions additionally exercise persistence/replay through the API.

Remote CI status belongs to the PR checks. Offline passes, the seven development probes and pending human review are separate evidence categories.
