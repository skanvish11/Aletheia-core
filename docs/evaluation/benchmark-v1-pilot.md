# Original-claim pilot results

Recorded **30 of 30** planned claims. Unrun: **0**.

**These are execution results and agreement with proposed labels, not human-verified accuracy.** All pilot labels and sources require independent review. Partial, failed, clarification and runner-failed attempts remain in the denominator. Citation support and correction quality remain unscored until reviewed.

| Metric | Result |
| --- | ---: |
| Completed investigations | 3/30 |
| Failed investigations | 17 |
| Partial investigations | 5 |
| Clarification requested | 5 |
| Runner failures | 0 |
| Completion rate | 10.0% |
| Provisional decision-label agreement | 3.3% |
| Macro F1 over represented classes | 0.044 |
| Median / p95 elapsed seconds | 15.17 / 58.55 |
| Observed network attempts | 333 |
| Observed input / output tokens | 729853 / 56797 |
| Billed cost and cost per correct answer | Unknown |
| Human-reviewed citation precision / coverage | Pending |

The label-agreement interval is descriptive and assumes independent observations. It does not measure uncertainty in the proposed labels or estimate accuracy on real user traffic. 95% Wilson interval: [0.005908590381612455, 0.16670390991409173].

## Confusion matrix

Rows are primary proposed labels. Columns are completed backend decisions; `no_decision` includes execution failures and clarification requests. An Almost label match still needs a supported correction to count as fully correct.

| Expected | True | False | Almost | Insufficient | Conflict | No decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| true | 1 | 0 | 0 | 0 | 0 | 5 |
| false | 0 | 0 | 0 | 0 | 0 | 6 |
| almost | 2 | 0 | 0 | 0 | 0 | 4 |
| insufficient_evidence | 0 | 0 | 0 | 0 | 0 | 6 |
| conflicting_evidence | 0 | 0 | 0 | 0 | 0 | 6 |

## Recorded diagnostic patterns

Counts are claims with each diagnostic, not mutually exclusive root causes. A recovered intermediate error may also appear on a completed run.

| Diagnostic | Claims |
| --- | ---: |
| clarification_shape | 8 |
| citation_spans | 7 |
| factual_uncertainty | 7 |
| model_finalization_reserve | 6 |
| scope_flag | 3 |
| correction_insufficient | 2 |
| query_identity | 1 |
| explanation_indices | 1 |
| clear_claim_reason | 1 |
| synthesis_coverage | 1 |

## Every attempt

| Claim ID | Proposed label | Status | Completed decision | Seconds |
| --- | --- | --- | --- | ---: |
| b0001 | true | failed | no_decision | 17.17 |
| b0002 | false | failed | no_decision | 2.08 |
| b0003 | almost | failed | no_decision | 19.74 |
| b0004 | insufficient_evidence | failed | no_decision | 2.59 |
| b0005 | conflicting_evidence | failed | no_decision | 2.84 |
| b0006 | true | partial | no_decision | 18.69 |
| b0007 | false | needs_clarification | no_decision | 2.54 |
| b0008 | almost | completed | true | 15.17 |
| b0009 | insufficient_evidence | failed | no_decision | 2.58 |
| b0010 | conflicting_evidence | partial | no_decision | 46.89 |
| b0011 | true | completed | true | 18.64 |
| b0012 | false | failed | no_decision | 45.50 |
| b0013 | almost | completed | true | 58.55 |
| b0014 | insufficient_evidence | failed | no_decision | 36.63 |
| b0015 | conflicting_evidence | needs_clarification | no_decision | 2.34 |
| b0016 | true | failed | no_decision | 14.86 |
| b0017 | false | needs_clarification | no_decision | 2.07 |
| b0018 | almost | failed | no_decision | 61.61 |
| b0019 | insufficient_evidence | needs_clarification | no_decision | 1.31 |
| b0020 | conflicting_evidence | failed | no_decision | 53.33 |
| b0021 | true | failed | no_decision | 40.96 |
| b0022 | false | failed | no_decision | 2.84 |
| b0023 | almost | partial | no_decision | 43.30 |
| b0024 | insufficient_evidence | needs_clarification | no_decision | 1.31 |
| b0025 | conflicting_evidence | failed | no_decision | 54.87 |
| b0026 | true | partial | no_decision | 18.71 |
| b0027 | false | failed | no_decision | 2.08 |
| b0028 | almost | partial | no_decision | 16.19 |
| b0029 | insufficient_evidence | failed | no_decision | 2.84 |
| b0030 | conflicting_evidence | failed | no_decision | 2.59 |

## Reproducibility and limits

Model: `nvidia/Nemotron-3_5-Lightning`. Thinking control: `disabled`. Concurrency: 1.

Selected dataset hash: `3fae8be9364af939dcfbaf289cfa0a71be275dea0081e1a01b8c5ecfa5cd7185`. Implementation hash at launch: `fc966664ed103652e1d1c5406887c8d17ab7ea3d2dd841c147cdd3eb97b11080`.

Each investigation had a fresh database. No failed claim was replaced by a better retry. The final report counts all recorded attempts. Candidate-generation requests are separate from these pilot usage totals. Report-generation and candidate-generation tooling may be updated while the pilot runs; backend prompts and research budgets remain fixed.

Saved-read and replay checks passed, by check: `{'same_saved_response': 30, 'zero_provider_calls': 30, 'ordered_events': 30, 'reconnect_replay': 30}`.

No positive qualification flags are expected in this pilot; flag recall is unmeasured. Six Almost and six conflict labels are hypotheses requiring particular scrutiny. Some insufficient-evidence cases are future counterfactuals whose input suitability also needs review.

## Agent inspection of all completed outputs

These observations are in `agent-review.json`; independent human review remains pending.

- **b0008:** Interpretation dropped the disputed smallpox eradication date and checked only the causal agent. A Wikipedia navigation link was accepted as supporting evidence. The FDA passage supports the causal agent but does not settle the omitted date.
- **b0011:** The saved passages support the SHA-256 digest-size claim. The explanation nevertheless claimed three independent sources when the evidence records came from two pages on one publisher, with independence marked unknown.

- **b0013:** The verdict is True for a claim saying May 1993, but the explanation explicitly says April 30, 1993. The interpreted assertion retains the wrong month; the verdict does not reflect the correction in its own explanation.

## Next work

Prioritize retaining every checkable detail during interpretation, enforcing exact-span support and source independence in the final explanation, and addressing interpretation repair failures and research-call exhaustion. Reconcile reference labels and evidence before expanding live evaluation. Preserve this baseline when testing fixes.
