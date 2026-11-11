# Same 30-claim pilot: repairs and rerun

The original 30 claims were rerun once after backend changes. No additional evaluation claims were generated. Original labels and baseline artifacts were preserved. These are proposed labels, so agreement below is provisional, not independently verified accuracy.

**This rerun is not an efficacy improvement:** agreement remains 1/30, completion fell from 3/30 to 2/30, and a false True verdict still passed semantic checking. Mechanical validation improved, but unnecessary clarification and evidence reasoning remain unresolved.

## Outcome comparison

| Measure | Original | Repaired rerun |
| --- | ---: | ---: |
| completed | 3 | 2 |
| failed | 17 | 11 |
| partial | 5 | 5 |
| needs_clarification | 5 | 12 |
| Completion rate | 0.100 | 0.067 |
| Provisional label agreement | 0.033 | 0.033 |
| Macro F1, five represented classes | 0.044 | 0.050 |
| Per-claim latency p50, seconds | 15.2 | 23.9 |
| Per-claim latency p95, seconds | 58.6 | 63.5 |
| Observed network attempts | 333 | 380 |
| Observed prompt_tokens | 729853 | 939529 |
| Observed completion_tokens | 56797 | 65573 |

Failures and partial runs remain in the 30-case denominator. An Almost label may additionally require correction review. Billed cost and human-verified citation quality are unknown.

## Why the original pilot failed

- Eight of the 17 failed investigations ended during interpretation: the model confused an unknown or false fact with missing user scope, or returned contradictory clarification fields.
- Seven cases encountered invalid passage-ID lists. Three failed investigations ended in evidence assessment. Some individual validation errors were repaired and are counted in more than one category.
- Six cases hit the model finalization reserve. The old quick profile had four research calls, exactly enough for interpretation, planning, and two assessments, leaving no repair capacity.
- The remaining failed investigations ended in synthesis (two), explanation-index validation (one), or final semantic rejection (three).
- Published answers also had semantic defects: b0008 dropped the disputed eradication year, b0013 said True while its explanation changed the month, and b0011 overstated source independence.
- The baseline had 332 successful provider attempts and one response-size failure. Missing credentials were not the cause of these pilot failures.

## Implemented changes

- Interpretation chooses the clarification branch before emitting assertions/questions; generation excludes factual uncertainty as a clarification category. The complete original claim text is retained for claims within the assertion limit without an explicit timeframe override.
- Each evidence-generation schema offers only that snapshot and its supplied passage IDs. Citation ordering and duplicate references are normalized without changing selected passages; nonexistent references still fail local validation.
- Standalone headings and navigation anchors cannot establish factual support or contradiction. Navigation-only spans are omitted from assessment inputs.
- Evidence instructions distinguish a contradictory date for the same event from evidence about a different event or population, and require checking descriptive clauses.
- Final checking requires explicit support for the decision as well as the prose. Explanation indices are constrained to supplied zero-based units. Instructions prohibit unsupported independence claims.
- Quick model budget increased from 8 to 10 calls, with four calls and 45 seconds still reserved for finalization; deep remains 16 and hard deadlines remain 120/240 seconds.

## Diagnostics before and after

| Code (cases encountering it) | Original | Rerun |
| --- | ---: | ---: |
| citation_spans | 7 | 0 |
| clarification_shape | 8 | 0 |
| clear_claim_reason | 1 | 1 |
| correction_insufficient | 2 | 0 |
| explanation_indices | 1 | 0 |
| factual_uncertainty | 7 | 0 |
| model_finalization_reserve | 6 | 3 |
| query_coverage | 0 | 1 |
| query_identity | 1 | 1 |
| scope_flag | 3 | 12 |
| synthesis_coverage | 1 | 0 |

Counts overlap and include repaired errors; absence of a formatting error does not establish factual correctness.

## Controls and verification

- Dataset hash: `3fae8be9364af939dcfbaf289cfa0a71be275dea0081e1a01b8c5ecfa5cd7185`; identical ordered case IDs and provider settings verified against baseline.
- Model: `nvidia/Nemotron-3_5-Lightning`; thinking `disabled`; output cap 4096.
- Rerun used three independent claims concurrently; baseline used one. Retrieval is live and can change. Latencies therefore are descriptive, not a controlled performance comparison.
- Backend/script hash at rerun start: `54947f11030f73b0b91dba5f4d383b63e85aeaf1c6ba19753d5e9035a0fe6829`.
- Offline suite: 387 passed, 2 existing expected failures. Ruff lint/format and git diff whitespace checks passed. A process-local mutation removing the navigation guard made both navigation regression cases fail as expected; production code was not altered.
- The two expected failures concern semantically misleading clarification questions and mutually agreeing but unsupported evidence assessments. The changes do not claim to solve general model reasoning reliability.
- Fresh per-case databases, saved-read/restart checks, and complete raw evidence/events are retained under `data/benchmark-v1-pilot-repaired/`. Baseline remains under `data/benchmark-v1-pilot/`.

## Per-claim comparison

| Case | Expected | Original status / prediction | Rerun status / prediction | Label match |
| --- | --- | --- | --- | --- |
| b0001 | true | failed / no_decision | partial / no_decision | False |
| b0002 | false | failed / no_decision | partial / no_decision | False |
| b0003 | almost | failed / no_decision | failed / no_decision | False |
| b0004 | insufficient_evidence | failed / no_decision | needs_clarification / no_decision | False |
| b0005 | conflicting_evidence | failed / no_decision | failed / no_decision | False |
| b0006 | true | partial / no_decision | failed / no_decision | False |
| b0007 | false | needs_clarification / no_decision | needs_clarification / no_decision | False |
| b0008 | almost | completed / true | partial / no_decision | False |
| b0009 | insufficient_evidence | failed / no_decision | needs_clarification / no_decision | False |
| b0010 | conflicting_evidence | partial / no_decision | needs_clarification / no_decision | False |
| b0011 | true | completed / true | partial / no_decision | False |
| b0012 | false | failed / no_decision | failed / no_decision | False |
| b0013 | almost | completed / true | failed / no_decision | False |
| b0014 | insufficient_evidence | failed / no_decision | failed / no_decision | False |
| b0015 | conflicting_evidence | needs_clarification / no_decision | needs_clarification / no_decision | False |
| b0016 | true | failed / no_decision | partial / no_decision | False |
| b0017 | false | needs_clarification / no_decision | failed / no_decision | False |
| b0018 | almost | failed / no_decision | needs_clarification / no_decision | False |
| b0019 | insufficient_evidence | needs_clarification / no_decision | needs_clarification / no_decision | False |
| b0020 | conflicting_evidence | failed / no_decision | needs_clarification / no_decision | False |
| b0021 | true | failed / no_decision | failed / no_decision | False |
| b0022 | false | failed / no_decision | needs_clarification / no_decision | False |
| b0023 | almost | partial / no_decision | completed / true | False |
| b0024 | insufficient_evidence | needs_clarification / no_decision | needs_clarification / no_decision | False |
| b0025 | conflicting_evidence | failed / no_decision | failed / no_decision | False |
| b0026 | true | partial / no_decision | completed / true | True |
| b0027 | false | failed / no_decision | failed / no_decision | False |
| b0028 | almost | partial / no_decision | failed / no_decision | False |
| b0029 | insufficient_evidence | failed / no_decision | needs_clarification / no_decision | False |
| b0030 | conflicting_evidence | failed / no_decision | needs_clarification / no_decision | False |

## Remaining semantic issues

- The rerun still contains unnecessary clarification requests. For example, b0004 asks for a specific region of Europa when the claim itself is a general existence claim.
- b0002 contains an assessment marked supports whose own rationale says Mercury is closer to the Sun. Another contradicting assessment was excluded by a false scope_match value. Valid reference IDs do not fix that logical contradiction.
- Evidence adequacy and routing can remain limiting even after a later authoritative record is retrieved: b0001 reached deep research and did not establish the required independent origins or untruncated synthesis.
- b0023 still returns True for a discovery year of 1798 while its own cited passages and explanation give 1799. This passed the new decision checker: model agreement is not an independent correctness guarantee.
- b0026 matches the proposed True label and has direct support in official UN passages, but one extra citation concerns entry into force rather than the adoption date and is incorrectly classified as direct support.
- b0019 and b0029 are future counterfactuals whose proposed labels expect insufficient evidence, while the current backend contract requests clarification for predictions. This mismatch requires review, not silent relabeling.
- These observations are inspection of saved traces, not independent human truth or citation adjudication. Additional remaining completed-output observations are recorded in agent-review.json.
