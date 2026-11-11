# Phase 1 reviewed PR: live 30-claim rerun

All 30 original claims were run once after fixing the four adversarial review findings. The result does **not demonstrate improved end-to-end performance**: **zero completed factual outcomes, 14 failed runs, 15 partial runs, and one unsupported-method response**. Historical label agreement is **0/30**, compared with **1/30** in the prior repaired pilot. The historical labels are AI proposals, so this is not independently verified factual accuracy.

## Results

| Measure | Prior repaired pilot | Reviewed Phase 1 PR |
| --- | ---: | ---: |
| Claims attempted | 30 | 30 |
| Completed factual outcomes | 2 | 0 |
| Unsupported-method responses | 0 | 1 |
| Partial | 5 | 15 |
| Failed | 11 | 14 |
| Needs clarification | 12 | 0 |
| Historical label matches, all cases | 1/30 | 0/30 |

The sole API `completed` response is b0004 (Europa), with `stop_reason=unsupported_method`, `result=null`, and method `scientific_inference`. It is not a factual completion or a label match. All 15 partial cases retain an `insufficient_evidence` result and zero saved evidence assessments; none published True, False, or Almost. No claim was retried as a fresh investigation, skipped, or removed from the denominator.

## What stopped the runs

Twelve failures occurred during interpretation, one during planning (b0007), and one during semantic final checking (b0012). Across all statuses, terminal stop reasons were 23 `invalid_task_output`, five `budget_exhausted`, one `semantic_rejection`, and one `unsupported_method`. All 222 observed provider requests (129 Nebius, 93 Tavily) returned HTTP 200. HTTP success does not imply valid model output.

| Validation code | Cases with at least one occurrence |
| --- | ---: |
| `comparison_values` | 15 |
| `response_schema` | 12 |
| `component_wording` | 8 |
| `scope_flag` | 4 |
| `citation_spans` | 3 |
| `query_capacity` | 1 |
| `query_gap` | 1 |
| `comparison_relation` | 1 |
| `provenance` | 1 |

Counts overlap. The evidence supports several concrete blockers:

- **Interpretation and exact wording:** Apollo, JWST, and Rosetta Stone fail `component_wording` on both interpretation attempts. This code can mean non-verbatim component text, missing numeric details, or changed assertion wording. Rejected raw responses are not retained, so the trace cannot identify the exact branch for each rejection.
- **Assessment contract:** `comparison_values` occurs in 15 cases, including direct non-comparison claims. The validator uses this code for several conditions, including values attached to a component without a comparison specification, duplicate sides, and ungrounded source text or numbers. The trace establishes repeated rejection, not which condition caused every instance.
- **Method routing:** Venus is classified as `record_lookup` with no comparison specifications. The resveratrol and Copilot intervention claims also receive `record_lookup`; mammography and the New Jersey employment claim receive `record_comparison`. These classifications do not implement the intended separation of direct records from causal/inference research. This is an implementation review finding, not a medical or economic verdict on those claims.
- **Budget pressure:** repeated invalid outputs consume the bounded repair allowance. Several subsequent assessment calls are blocked by the finalization reserve. Increasing budgets alone would not resolve invalid schemas, routing, or extraction.
- **Final checking:** Python release-date case b0012 retains three evidence records, but final checking rejects the decision after a bounded semantic repair. Two restricted diagnostic files preserve the failed conditions; no unchecked verdict is published.

## Six earlier problem cases

| Case | Reviewed result | What this establishes |
| --- | --- | --- |
| b0001 Apollo | Failed: interpretation wording | Passage-selection improvements were not exercised end to end. |
| b0002 Venus | Partial: invalid assessment | No false conflict verdict, but still no resolved comparison. |
| b0004 Europa | Unsupported scientific inference | Explicit method limitation replaces the previous unnecessary clarification. |
| b0006 Antibiotics | Partial: invalid assessment | Did not reach successful factual finalization. |
| b0023 Rosetta Stone | Failed: interpretation wording | The previous incorrect True was not repeated, but there is no successful correction. |
| b0028 Montreal Protocol | Partial: exhausted budget | No completed assessment or corrected verdict. |

## Reproduction and limits

- Evaluated revision: `c885bbad8c4fb29a619bdf41236c95b94ef003ed`; root and all per-case working trees were clean when recorded.
- Dataset SHA-256: `3fae8be9364af939dcfbaf289cfa0a71be275dea0081e1a01b8c5ecfa5cd7185`; exact original ordered 30 cases and labels preserved.
- Run: `2026-11-11T03:51:26.691350+00:00` to `2026-11-11T03:56:42.698532+00:00`; 316.0 seconds wall time.
- Model: `nvidia/Nemotron-3_5-Lightning`; `json_schema`; thinking disabled; 4,096 output-token limit; 45-second provider timeout; two configured provider retries; concurrency three. All public provider settings match the prior repaired pilot.
- Application limits differ: this PR uses eight quick-run model attempts versus ten in the prior archived runtime, with four attempts reserved for finalization in both. Deep runs retain 16 model attempts; quick/deep deadlines are 120/240 seconds. The run used the current PR unchanged. Live sources and model outputs can vary; this is not a controlled causal estimate of the four fixes.
- Observed usage: 519,496 prompt tokens and 84,807 completion tokens. These are reported task usage totals, not a complete billing statement; cost is unknown.
- All 30 cases passed saved-response identity, zero-provider-call reads/reuse, ordered events, reconnect replay, and unchanged read-only restart with zero provider calls. There were no runner failures or early stops.
- Offline checks: 430 passed, one existing expected failure; Ruff passed for 131 files; all 22 deliberate faults detected. [CI for the evaluated code](https://github.com/skanvish11/Aletheia-core/actions/runs/42955446086) passed Python 3.12/3.13 and Linux/Windows local-server checks. The four adversarial defects are covered by 15 regression probes. These controlled tests do not establish live research quality.
- Original handoff integrity: all 110 historical files verified unchanged. This is a reused development set; independent human labeling, citation acceptance, and the planned Phase 1 acceptance evaluation remain pending.

The next development work should isolate routing, exact component preservation, and assessment-output failures using small controlled cases before another full live run. Do not claim Phase 1 acceptance or attribute the lower result to the four fixes alone.

## All 30 cases

The [machine-readable results](phase-one-reviewed-pilot-results.json) include sanitized settings, per-case diagnostics, usage, and persistence checks. Full local traces, source snapshots, databases and restricted diagnostics remain in ignored `data/phase-one-pilot-reviewed-20261110/`. Raw provider responses and credentials are not included. The [prior pilot table](pilot-handoff/cases.md) preserves the earlier outcomes.

| Case | Original claim | Status | Stop reason | Stored outcome |
| --- | --- | --- | --- | --- |
| b0001 | The Apollo 11 lunar module landed on the Moon on 20 July 1969. | failed | `invalid_task_output` | none |
| b0002 | Venus is the closest planet to the Sun. | partial | `invalid_task_output` | insufficient_evidence |
| b0003 | The James Webb Space Telescope, launched in November 2021, observes the universe primarily in infrared light. | failed | `invalid_task_output` | none |
| b0004 | Microbial life exists beneath the present-day ice shell of Europa. | completed | `unsupported_method` | unsupported_method |
| b0005 | The Younger Dryas cooling event was triggered by an extraterrestrial impact approximately 12,800 years ago. | failed | `invalid_task_output` | none |
| b0006 | Antibiotics do not treat infections caused solely by viruses. | partial | `invalid_task_output` | insufficient_evidence |
| b0007 | The measles, mumps and rubella vaccine has been shown to cause autism. | failed | `invalid_task_output` | none |
| b0008 | Smallpox, declared eradicated by the World Health Assembly in 1979, is caused by variola virus. | partial | `invalid_task_output` | insufficient_evidence |
| b0009 | Daily oral resveratrol supplementation extends lifespan in healthy adult humans. | partial | `budget_exhausted` | insufficient_evidence |
| b0010 | Annual mammography screening starting at age 40 reduces all-cause mortality in average-risk women compared with no screening. | partial | `budget_exhausted` | insufficient_evidence |
| b0011 | The SHA-256 cryptographic hash algorithm produces a 256-bit digest. | partial | `invalid_task_output` | insufficient_evidence |
| b0012 | The original version of the Python programming language was first publicly released in 2001. | failed | `semantic_rejection` | none |
| b0013 | The World Wide Web software, released by CERN into the public domain in May 1993, enabled royalty-free reuse. | failed | `invalid_task_output` | none |
| b0014 | GPT-4 was trained with exactly 1.76 trillion parameters. | failed | `invalid_task_output` | none |
| b0015 | Using GitHub Copilot increases experienced professional developers’ productivity on unfamiliar software engineering tasks. | partial | `invalid_task_output` | insufficient_evidence |
| b0016 | The United States Consumer Price Index measures price changes for a basket of consumer goods and services. | partial | `invalid_task_output` | insufficient_evidence |
| b0017 | Nominal gross domestic product removes the effects of price inflation from measured economic output. | partial | `invalid_task_output` | insufficient_evidence |
| b0018 | The euro, introduced as physical banknotes and coins in 2001, is the shared currency of the euro area. | partial | `budget_exhausted` | insufficient_evidence |
| b0019 | A United States federal minimum wage of $25 per hour in 2030 would increase total national employment during that year. | failed | `invalid_task_output` | none |
| b0020 | New Jersey’s April 1992 minimum wage increase reduced employment at fast-food restaurants relative to eastern Pennsylvania. | partial | `invalid_task_output` | insufficient_evidence |
| b0021 | The Berlin Wall opened to cross-border travel on 9 November 1989. | partial | `invalid_task_output` | insufficient_evidence |
| b0022 | The Magna Carta of 1215 was issued during the reign of King Henry VIII of England. | failed | `invalid_task_output` | none |
| b0023 | The Rosetta Stone, discovered in Egypt in 1798, helped scholars decipher Egyptian hieroglyphs. | failed | `invalid_task_output` | none |
| b0024 | The unidentified author known as Jack the Ripper was the painter Walter Sickert. | failed | `invalid_task_output` | none |
| b0025 | The Bronze Age eruption of Thera occurred before 1600 BCE. | partial | `invalid_task_output` | insufficient_evidence |
| b0026 | The Paris Agreement was adopted at the United Nations climate conference in December 2015. | partial | `budget_exhausted` | insufficient_evidence |
| b0027 | The United States Constitution sets a six-year term for members of the House of Representatives. | failed | `invalid_task_output` | none |
| b0028 | The Montreal Protocol, adopted in 1986, regulates substances that deplete the ozone layer. | partial | `budget_exhausted` | insufficient_evidence |
| b0029 | A nationwide four-day working week enacted in India in 2030 would reduce annual carbon emissions by exactly 10 percent. | failed | `invalid_task_output` | none |
| b0030 | United States right-to-carry handgun laws reduce the violent crime rate compared with retaining more restrictive carry laws. | failed | `invalid_task_output` | none |
