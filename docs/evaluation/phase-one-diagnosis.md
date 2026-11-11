# Pilot diagnosis and the decision to narrow phase one

This analysis explains why the next implementation focuses on direct facts and comparisons. It is based on the saved 30-claim pilot, its repaired rerun, and a read-only trace of six representative failures. It separates observed defects from proposed remedies. The six cases were selected for diagnosis, not sampled to estimate the prevalence of each defect.

## How we got here

1. The original objective was a 1,500-claim dataset and an efficacy evaluation. A 30-claim pilot was prioritized before scaling.
2. The original pilot recorded 3 completed investigations, 17 failed, 5 partial, and 5 clarification requests. One of 30 matched its proposed label. Two of the completed answers had incorrect True decisions against their proposed Almost labels.
3. Mechanical repairs preserved original claim wording, constrained citation identifiers, filtered some navigation content, added two quick-research repair calls, and strengthened the explanation check. They did not establish reliable factual reasoning.
4. The same 30 unchanged claims were rerun. There were 2 completed investigations, 11 failed, 5 partial, and 12 clarification requests. Provisional agreement remained 1/30. Invalid citation-list errors fell from seven cases to zero, but completion fell from 10% to 6.7%.
5. Six saved cases were traced without provider calls or label changes. The analysis found relevant evidence excluded from model input, evidence misclassified despite explicit facts in the passages, route-dependent decision thresholds, and avoidable loss of investigation progress.
6. We considered whether topic breadth was the primary cause. The cases do not establish that hypothesis: several already contained the needed facts. Each claim ran independently. A more useful initial boundary is the required research method, rather than history versus astronomy versus health.
7. The agreed next phase supports direct facts and direct comparisons, identifies unsupported methods, and evaluates routing/parsing separately from factual quality. The proposed 1,000-claim recognition set is future work. It has not been generated.

The labels remain AI proposals with no completed independent human acceptance. Therefore 1/30 is failure-inclusive agreement with proposed labels, not a validated estimate of real-world accuracy. Poor labels cannot explain away the concrete internal contradictions documented below. The original and rerun used the same provider settings but concurrency changed from one to three; the live web can also change. This is not a controlled causal estimate of each code change's effect.

## Six traced failures

### b0004 Europa life stops before research

Claim: “Microbial life exists beneath the present-day ice shell of Europa.”

The interpreter asks which region, geological formation, or habitat is intended. Event 9 labels the problem `missing_scope`; the investigation ends after one model call and zero searches. The submitted assertion is a general existence claim. These additional regional restrictions are not required to preserve its meaning.

The claim validator checks whether questions and assertions have a consistent shape, but does not independently establish that the requested clarification is necessary. The controller accepts the classification and stops immediately. In phase one, a claim requiring scientific inference may instead be explicitly unsupported; that must remain distinct from missing scope.

Evidence: [saved case and events](pilot-handoff/rerun/cases/b0004.json), [claim validation](pilot-handoff/rerun-runtime/src/aletheia/claims.py), [controller](pilot-handoff/rerun-runtime/src/aletheia/orchestrator.py).

### b0001 Apollo landing excludes an available answer and changes the evidence threshold

Claim: “The Apollo 11 lunar module landed on the Moon on 20 July 1969.”

The saved Wikipedia snapshot has 560 spans. Replaying the selector against that snapshot selects 120 spans ending at ID 168, dominated by navigation and language links. The landing-date entry is span 241, outside the input supplied to the model. The navigation filter removes headings and fragment links but misses these language/navigation links.

Later research obtains direct supporting passages and evidence classified as an authoritative record. Event 52 has already escalated the investigation from quick to deep. In `sufficient`, a single authoritative record qualifies under quick rules, while deep requires an eligible synthesis or distinct independent origins. The available synthesis sources carry truncation limitations, and the established origins do not form an independent pair. Replaying the decision function with identical saved evidence produces True under quick and insufficient evidence under deep. This replay proves a policy inconsistency; it does not independently validate every source-quality judgment made by the model.

The investigation ends at event 134 with `followup_round_limit`, not a wall-clock timeout. Its final prose describes support and independent sources while the structured result says insufficient evidence, revealing an additional explanation/decision consistency failure.

Evidence: [saved case](pilot-handoff/rerun/cases/b0001.json), [selected spans and excluded span 241](pilot-handoff/apollo-selection.json), [selector](pilot-handoff/rerun-runtime/src/aletheia/verification.py), [sufficiency rules](pilot-handoff/rerun-runtime/src/aletheia/verdicts.py).

### b0002 Venus distance manufactures a conflict and wastes the last search round

Claim: “Venus is the closest planet to the Sun.”

The interpreted assertion is preserved but classified as `generalized`, which selects deep research even though the model recommends quick. One saved passage gives Mercury's average orbital distance as 58 million km and Venus's as 108 million km. Its assessment labels this `supports`, while its own rationale says Mercury is closer. A different contradicting assessment is excluded because `scope_match=false`.

When another contradiction is admitted, the controller sees both support and contradiction and declares conflicting evidence. The cited passages do not establish that disagreement; inconsistent assessments created it.

The last plan also proposes three queries with only two search attempts remaining. Events 108 and 112 record successful searches; event 114 rejects the third at the search limit. Because gathering waits for the whole query loop before extracting pages, the two completed queries in this round do not reach extraction. The validator checks identity and coverage but does not enforce the remaining query count.

Evidence: [saved case and events 100 through 117](pilot-handoff/rerun/cases/b0002.json), [planning validation](pilot-handoff/rerun-runtime/src/aletheia/planning.py), [gathering loop](pilot-handoff/rerun-runtime/src/aletheia/research.py).

### b0023 Rosetta Stone passes a contradiction through the entire decision chain

Claim: “The Rosetta Stone, discovered in Egypt in 1798, helped scholars decipher Egyptian hieroglyphs.”

The saved passages distinguish the 1798 Egyptian campaign from the 1799 discovery. Assessments merge them into supporting evidence; one secondary history page is also classified as an authoritative record. The controller computes True from those assessment fields.

`correction_eligible` excludes a preliminary True, so synthesis cannot offer an Almost correction at that point. The explanation itself mentions the 1799 finding while affirming the 1798 claim. The final checker accepts it. Original wording was preserved: this failure occurs in evidence interpretation, source classification, verdict computation, and semantic checking.

Reference validation and another call to the same model did not provide independent correctness assurance. The saved record proves that the True result is internally inconsistent; it does not prove which alternative model or prompting strategy would fix it.

Evidence: [saved case and cited passages](pilot-handoff/rerun/cases/b0023.json), [verdict and correction rules](pilot-handoff/rerun-runtime/src/aletheia/verdicts.py).

### b0028 Montreal Protocol loses progress after a rejected source assessment

Claim: “The Montreal Protocol, adopted in 1986, regulates substances that deplete the ozone layer.”

The first source, UNEP, supplies an adoption date of 16 September 1987. The saved assessment explicitly recognizes the discrepancy but labels it context, while another assessment supports only the regulatory-function portion of the claim.

Assessment of the second source fails twice, at events 51 and 56, with `scope_flag`: at least one assessment simultaneously claims full-scope support and carries a narrower-scope flag. The rejected response bodies are not retained, so their exact wording cannot be reconstructed. Rejecting that inconsistent assessment is appropriate. The controller's handling of the resulting `InvalidTask` terminates the whole investigation instead of preserving the earlier valid evidence for further bounded handling.

The final stop reason is `provider_failure`, although the recorded provider attempts succeeded. This conflates internal task-validation failure with provider failure. In addition, the assessment prompt mixes instructions to treat a differing date for the same event as contradiction with instructions to retain a corrected fact as context. That ambiguity is a plausible contributor, not a demonstrated sole cause.

Evidence: [saved case](pilot-handoff/rerun/cases/b0028.json), [assessment guard](pilot-handoff/rerun-runtime/src/aletheia/evidence.py), [assessment instructions](pilot-handoff/rerun-runtime/src/aletheia/verification.py), [controller exception handling](pilot-handoff/rerun-runtime/src/aletheia/orchestrator.py).

### b0006 Antibiotics reaches finalization but the veto is not fully observable

Claim: “Antibiotics do not treat infections caused solely by viruses.”

Supporting passages are retrieved. Event 79 stops research with `evidence_sufficient`; replaying the decision rules on saved assessments produces True. Synthesis and checker tasks return structurally valid responses at events 84 and 88. Event 89 then rejects the final explanation as `unsupported_explanation`, and event 90 records `provider_failure`.

The rejection is outside the task-level repair loop. The controller terminates without publishing the preliminary result. The stored diagnostic does not distinguish a false `decision_supported` from an incomplete set of supported explanation units. Neither the rejected explanation nor the structured checker result is retained in research records. Therefore the trace locates the failure but cannot establish whether the checker correctly rejected bad prose or incorrectly vetoed an otherwise supported answer.

The saved metadata also shows that the deep-evidence gate qualified a video transcript as a credible synthesis while disqualifying a written synthesis with a truncated input window. That is a source-quality policy concern, not proof that a final unchecked verdict should have been published. Its classification under phase one's narrower research methods needs separate review.

Evidence: [saved case](pilot-handoff/rerun/cases/b0006.json), [final-check conditions](pilot-handoff/rerun-runtime/src/aletheia/verdicts.py), [saved task diagnostics](pilot-handoff/rerun-runtime/src/aletheia/tasks.py).

## What the evidence supports next

The [phase-one plan](../direct-claims-phase-one.md) addresses these findings through relevant passage selection, component-level assessment, deterministic comparisons where operands are grounded, consistent evidence requirements, explicit unsupported-method handling, and bounded failure recovery. It also requires safe structured diagnostics that identify semantic-check failures.

The records do not establish that a narrower topic selection, reasoning enabled, a different model, or a rewritten prompt will achieve the target scores. Those remain hypotheses for controlled development evaluations. Neither the 1,000-claim dataset nor phase-one implementation is part of this evidence handoff.
