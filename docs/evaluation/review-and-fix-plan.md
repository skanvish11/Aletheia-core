# Evaluation review and proposed repair plan

Prepared from the frozen November 5, 2026 run. This preserves the original findings and repair plan. Implementation progress and all follow-up attempts are tracked separately in [first repairs](repairs.md); the baseline below has not been rewritten to match newer outcomes.

**This is a useful first baseline, and it exposes substantial live execution problems.** We ran 20 proposed claims: 13 failed, 2 were partial, 5 asked for clarification, and 0 completed. Those are execution outcomes—not evidence that the system answered 20 factual questions incorrectly.

The proposed answers have not been approved by human reviewers. In particular, Almost and conflict labels are hypotheses for review, not ground truth.

## What the baseline establishes

- **11 claims** failed at evidence checking after one source had been saved; none of these had an evidence assessment. A shared failure in that stage is a strong lead. Truncation was confirmed in a separate Apollo diagnostic, not individually established for all 11.
- **2 claims** failed at the interpretation deadline before any search.
- **2 claims** returned partial insufficient-evidence results after deadlines, with no final explanation citations.
- **5 claims** asked questions instead of searching. The questions generally ask the user to supply a research conclusion, rather than clarify meaning.
- **0 completed results** means we cannot yet evaluate successful True/False/Almost decisions, grounded corrections, completed conflict handling, or citation accuracy.

## What worked

- 307 offline tests passed. They establish the tested behavior under synthetic inputs, not real research quality.
- Saved result reuse, zero provider calls on saved reads, ordered persisted events, API replay after a cursor, and unchanged records after a read-only restart passed for all 20 baseline cases.
- Refresh created a separate version and retries reused it without changing the original, but the refreshed research itself failed.
- Search and extraction did work for the 11 cases that reached evidence checking. The diagnosed Apollo failure happened on the model assessment call; it was not a Tavily retrieval failure.

## Issue register

| ID | Issue | Evidence level |
| --- | --- | --- |
| [F01](#f01) | Incomplete failure diagnostics | Confirmed reporting gap |
| [F02](#f02) | Model responses are cut off | Confirmed in diagnostic trials |
| [F03](#f03) | Model latency and deadlines prevent research | Confirmed |
| [F04](#f04) | Factual uncertainty is treated as a clarification request | Observed in five cases; scope review still needed |
| [F05](#f05) | Useful and authoritative evidence is not reliably selected | Observed; full prevalence unmeasured |
| [F06](#f06) | Verdict and citation quality are not yet measured | Unmet evaluation gate, not a proven classification bug |
| [F07](#f07) | The proposed dataset needs human review and broader coverage | Confirmed limitation |
| [F08](#f08) | Successful demo paths remain unproven | Unmet integration gate |

<a id="f01"></a>
### F01: Incomplete failure diagnostics

**Finding:** 11 baseline cases stop with generic provider_failure at evidence checking; each has one stored source and zero assessments. Only the separate diagnostic reveals the exact truncated_output code.

**Proposed work:** Persist safe stage, schema name, attempt duration, outcome/error code, finish reason and available usage for every attempted call, including failures. Do not retain private prompts or responses.

**Done when:** A failed run identifies the failed stage and safe cause without requiring another paid reproduction.

<a id="f02"></a>
### F02: Model responses are cut off

**Finding:** Apollo at 4,096 output tokens failed during assessment with truncated_output. The separate 8,192-token trial failed at synthesis; its refresh failed at assessment. This is not proof that all 11 baseline assessment failures had this cause.

**Proposed work:** Measure response size by task; bound assessment batches, requested fields and explanation length. Investigate how this model spends its output allowance. Test one change at a time; do not assume a larger cap fixes it.

**Done when:** A small, agreed set of clear claims completes with schema-valid, cited responses within declared limits. Retain all repeat attempts.

<a id="f03"></a>
### F03: Model latency and deadlines prevent research

**Finding:** t014 and t015 reached the deadline while interpreting, before search. t013 timed out during assessment; t018 also stopped at a deadline and returned partial insufficient evidence.

**Proposed work:** Measure latency by stage, separate slow service responses from application overhead, then adjust stage budgets and retry rules using those measurements. Preserve the hard overall limit and time to produce a checked final answer.

**Done when:** Simple claims finish within a declared budget; injected slow calls stop honestly, preserve useful work, and do not consume the entire finalization allowance.

<a id="f04"></a>
### F04: Factual uncertainty is treated as a clarification request

**Finding:** t005, t016, t017, t019 and t020 made no searches. Their questions asked whether the claim was true or what the evidence said. Examples are reproduced below.

**Proposed work:** Clarify only missing user scope, such as which product, location or period. Send an explicitly scoped factual question to research. Keep legitimate ambiguity and unsupported compound-input checks.

**Done when:** Clear false claims and unresolved scientific questions trigger research. Truly ambiguous inputs still ask a useful scope question. Human reviewers resolve the two proposed Almost cases.

<a id="f05"></a>
### F05: Useful and authoritative evidence is not reliably selected

**Finding:** The 8,192-token Apollo trial included a navigation link and secondary/shared-origin pages, without evidence accepted as an authoritative record. t013 reported navigation/heading-only passages and insufficient qualifying evidence.

**Proposed work:** Inspect search ranking, primary-source selection, extraction quality and passage selection separately. Filter boilerplate and select claim-relevant passages within the existing bounds. Search explicitly for missing primary records when the evidence gate requires them.

**Done when:** For straightforward record claims, the pipeline retrieves and cites a relevant original record when available. Navigation-only and syndicated pages cannot satisfy evidence requirements.

<a id="f06"></a>
### F06: Verdict and citation quality are not yet measured

**Finding:** No completed baseline investigation; both partial results have zero final explanation units. No successful Almost correction, resolved conflict or completed insufficient-evidence path was demonstrated.

**Proposed work:** After execution fixes, evaluate verdicts, correction grounding, citation support, flags and appropriate abstention separately. Do not lower evidence requirements to raise completion counts.

**Done when:** Human-reviewed reports cover every case, including incorrect answers, partials and failures; citation quality is not inferred from passing schema checks.

<a id="f07"></a>
### F07: The proposed dataset needs human review and broader coverage

**Finding:** All 20 labels are AI proposals. The two Almost cases and both conflict cases need explicit adjudication. The set is science/history-heavy and has only one expected flag. No held-out evaluation ran.

**Proposed work:** Review wording, scope, expected decisions and sources independently; record disagreements. Add relevant benchmark/comparison and flag cases. Keep the private held-out set separate. Preserve the original proposal and failed runs when revising cases.

**Done when:** An approved versioned acceptance set has defensible labels and useful category coverage. No post-hoc label changes merely to agree with the model; held-out results are reported separately.

<a id="f08"></a>
### F08: Successful demo paths remain unproven

**Finding:** Saved reads, replay and restart passed, but the live refresh also failed. No successful changed-evidence comparison or browser walkthrough was demonstrated.

**Proposed work:** After research works, demonstrate normal, insufficient, saved, refresh and reconnect paths through the actual client; retain an honestly labeled recorded fallback.

**Done when:** The demo uses inspectable real results, shows failure states and timestamps, and distinguishes recorded events from new provider calls.

## All 20 claims and their outcomes

Wording below is the exact submitted claim. Scope/context and reference links follow in the case details. “Proposed” describes the evaluator’s draft expectation, not an approved label.

| Case | Submitted claim | Proposed outcome | What happened |
| --- | --- | --- | --- |
| [t001](#t001) | Apollo 11 landed on the Moon on July 20, 1969. | true | Failed during evidence checking: generic provider failure |
| [t002](#t002) | Marie Curie won the Nobel Prize in Chemistry in 1903. | false | Failed during evidence checking: generic provider failure |
| [t003](#t003) | Tim Berners-Lee invented the World Wide Web at CERN in 1989. | true | Failed during evidence checking: generic provider failure |
| [t004](#t004) | The James Webb Space Telescope launched on December 25, 2021. | true | Failed during evidence checking: generic provider failure |
| [t005](#t005) | Albert Einstein’s 1921 Nobel Prize in Physics was awarded specifically for his theory of relativity. | false | Asked for clarification; no search |
| [t006](#t006) | Mercury is hotter on average at its surface than Venus. | false | Failed during evidence checking: generic provider failure |
| [t007](#t007) | Venus’s dense atmosphere makes its surface hotter through a greenhouse effect. | true | Failed during evidence checking: generic provider failure |
| [t008](#t008) | Northern Hemisphere summer is primarily caused by Earth being closer to the Sun. | false | Failed during evidence checking: generic provider failure |
| [t009](#t009) | Earth’s axial tilt is the primary cause of its annual seasons. | true | Failed during evidence checking: generic provider failure |
| [t010](#t010) | At higher elevations, lower atmospheric pressure makes water boil at a lower temperature. | true | Failed during evidence checking: generic provider failure |
| [t011](#t011) | Mount Everest is Earth’s highest mountain measured above mean sea level. | true | Failed during evidence checking: generic provider failure |
| [t012](#t012) | Mount Everest’s summit is the point on Earth’s surface farthest from Earth’s center. | false | Failed during evidence checking: generic provider failure |
| [t013](#t013) | Chimborazo’s summit is farther from Earth’s center than Mount Everest’s summit. | true | Partial: insufficient evidence after deadline |
| [t014](#t014) | Antarctica is a desert because it receives very little precipitation. | true | Failed during interpretation: deadline |
| [t015](#t015) | A light-year is a unit of time. | false | Failed during interpretation: deadline |
| [t016](#t016) | American scientist Tim Berners-Lee invented the World Wide Web at CERN in 1989. | almost | Asked for clarification; no search |
| [t017](#t017) | The James Webb Space Telescope was launched successfully in December 2021 aboard an Ariane 4 rocket. | almost | Asked for clarification; no search |
| [t018](#t018) | The present-day cosmic expansion rate is approximately 73 kilometers per second per megaparsec. | conflicting evidence | Partial: insufficient evidence after deadline |
| [t019](#t019) | Phosphine gas was present in Venus’s clouds during the observations reported by Greaves and colleagues in 2020. | conflicting evidence | Asked for clarification; no search |
| [t020](#t020) | The 1977 Wow! radio signal was produced by an extraterrestrial civilization. | insufficient evidence | Asked for clarification; no search |

## Exact clarification questions

| Case | Question returned by the application | Why review it |
| --- | --- | --- |
| t005 | Was the 1921 Nobel Prize in Physics awarded specifically for Einstein's theory of relativity? | Asks for the conclusion or evidence assessment the investigation should attempt. |
| t016 | Is Tim Berners-Lee correctly described as an American scientist? | Asks about a factual detail that could be researched; the proposed Almost label also needs human review. |
| t017 | Was the James Webb Space Telescope launched on an Ariane 4 or Ariane 5 rocket? | Asks about a factual detail that could be researched; the proposed Almost label also needs human review. |
| t019 | Do the independent reanalyses through December 2021 confirm or refute the presence of phosphine in Venus's clouds as reported by Greaves et al.? | Asks for the conclusion or evidence assessment the investigation should attempt. |
| t020 | Is there conclusive evidence that the 1977 Wow! radio signal originated from an extraterrestrial civilization? | Asks for the conclusion or evidence assessment the investigation should attempt. |

## Proposed fix order

Preserve the current dataset and artifacts as the baseline. Work in small changes with a stated hypothesis and an observable exit condition. Do not tune on the private held-out set.

| Order | Work package | First checks | Exit condition |
| --- | --- | --- | --- |
| 1 | Agree on a few clear claim scopes and capture complete safe diagnostics (F01/F07). | Apollo landing, Curie award category, Webb launch date. | Reviewers agree what is being asked; every failure has a safe stage/cause record. |
| 2 | Fix the shared evidence-assessment/output problem (F02), checking latency alongside it (F03). | Small bounded live runs on those same cases; preserve every repeat. | At least one complete result with an inspectable supported citation, then repeatable completion across the small set. |
| 3 | Fix interpretation and unnecessary clarification (F04), including early deadline failures (F03). | Einstein, light-year, Wow! signal; plus genuinely ambiguous counterexamples. | Clear claims research; missing scope clarifies; slow calls stay bounded. |
| 4 | Improve source and passage selection and targeted follow-ups (F05). | Everest/Chimborazo, then historical phosphine and expansion-rate cases. | Useful evidence reaches the assessment stage; qualifying sources and unresolved gaps remain visible. |
| 5 | Complete human dataset review and evaluate answer quality (F06/F07). | All 20 reviewed cases, with Almost/flag/conflict cases assessed separately. | Report complete-set outcomes and human citation checks; do not exclude partial or failed runs. |
| 6 | Verify refresh, the actual client and the demonstration (F08). | Normal, insufficient, saved, refresh and reconnect journeys. | Successful inspectable demo, truthful recorded fallback, and documented limitations. |

Dataset review can proceed while execution fixes are being developed. Do not spend another full 20-case batch on a known shared failure before the small checks show progress. Rerun the entire set after the relevant fix group to detect regressions. A model change, if needed, should be an explicit separately recorded experiment, not a silent fallback.

## Case details and evidence links

<a id="t001"></a>
### t001

Apollo 11 landed on the Moon on July 20, 1969.

- Draft expectation: **true**; type: direct_fact.
- Execution: **failed**; stop reason: `provider_failure`.
- Saved sources: 1; evidence assessments: 0; final explanation units: 0.
- [Exact local run artifact](../../data/evaluation-2026-11-05/t001.json).
- Submitted definitions: Use UTC/GMT for the landing date, not the later first moonwalk.
- [Reference 1](https://www.nasa.gov/wp-content/uploads/static/history/SP-4029/Apollo_11a_Summary.htm): The lunar module landed on 20 July 1969, using GMT.
- Review note: AI-proposed, source-referenced; not a blind human label. 

<a id="t002"></a>
### t002

Marie Curie won the Nobel Prize in Chemistry in 1903.

- Draft expectation: **false**; type: direct_fact.
- Execution: **failed**; stop reason: `provider_failure`.
- Saved sources: 1; evidence assessments: 0; final explanation units: 0.
- [Exact local run artifact](../../data/evaluation-2026-11-05/t002.json).
- [Reference 1](https://www.nobelprize.org/nomination/archive/show_people.php?id=2051&lang=en): Physics award in 1903; Chemistry award in 1911.
- Review note: AI-proposed, source-referenced; not a blind human label. The award category is central, not a minor correction.

<a id="t003"></a>
### t003

Tim Berners-Lee invented the World Wide Web at CERN in 1989.

- Draft expectation: **true**; type: direct_fact.
- Execution: **failed**; stop reason: `provider_failure`.
- Saved sources: 1; evidence assessments: 0; final explanation units: 0.
- [Exact local run artifact](../../data/evaluation-2026-11-05/t003.json).
- [Reference 1](https://home.cern/science/computing/the-birth-of-the-web): British scientist Tim Berners-Lee invented the Web at CERN in 1989.
- Review note: AI-proposed, source-referenced; not a blind human label. 

<a id="t004"></a>
### t004

The James Webb Space Telescope launched on December 25, 2021.

- Draft expectation: **true**; type: direct_fact.
- Execution: **failed**; stop reason: `provider_failure`.
- Saved sources: 1; evidence assessments: 0; final explanation units: 0.
- [Exact local run artifact](../../data/evaluation-2026-11-05/t004.json).
- [Reference 1](https://svs.gsfc.nasa.gov/14060): Launch occurred on 25 December 2021 aboard an Ariane 5.
- Review note: AI-proposed, source-referenced; not a blind human label. 

<a id="t005"></a>
### t005

Albert Einstein’s 1921 Nobel Prize in Physics was awarded specifically for his theory of relativity.

- Draft expectation: **false**; type: direct_fact.
- Execution: **needs_clarification**; stop reason: `not applicable`.
- Saved sources: 0; evidence assessments: 0; final explanation units: 0.
- [Exact local run artifact](../../data/evaluation-2026-11-05/t005.json).
- [Reference 1](https://www.nobelprize.org/prizes/physics/1921/ceremony-speech/): The award emphasizes the photoelectric effect, not relativity.
- Review note: AI-proposed, source-referenced; not a blind human label. Distinguish award year from the 1922 announcement.

<a id="t006"></a>
### t006

Mercury is hotter on average at its surface than Venus.

- Draft expectation: **false**; type: comparison.
- Execution: **failed**; stop reason: `provider_failure`.
- Saved sources: 1; evidence assessments: 0; final explanation units: 0.
- [Exact local run artifact](../../data/evaluation-2026-11-05/t006.json).
- [Reference 1](https://science.nasa.gov/mercury/facts/): Mercury is nearest the Sun but Venus is hotter.
- [Reference 2](https://science.nasa.gov/venus/venus-facts/): A dense atmosphere traps heat; Venus is hotter than Mercury.
- Review note: AI-proposed, source-referenced; not a blind human label. Do not confuse distance to the Sun with surface temperature.

<a id="t007"></a>
### t007

Venus’s dense atmosphere makes its surface hotter through a greenhouse effect.

- Draft expectation: **true**; type: causal.
- Execution: **failed**; stop reason: `provider_failure`.
- Saved sources: 1; evidence assessments: 0; final explanation units: 0.
- [Exact local run artifact](../../data/evaluation-2026-11-05/t007.json).
- [Reference 1](https://science.nasa.gov/venus/venus-facts/): A dense atmosphere traps heat; Venus is hotter than Mercury.
- [Reference 2](https://science.nasa.gov/mercury/facts/): Mercury is nearest the Sun but Venus is hotter.
- Review note: AI-proposed, source-referenced; not a blind human label. 

<a id="t008"></a>
### t008

Northern Hemisphere summer is primarily caused by Earth being closer to the Sun.

- Draft expectation: **false**; type: causal.
- Execution: **failed**; stop reason: `provider_failure`.
- Saved sources: 1; evidence assessments: 0; final explanation units: 0.
- [Exact local run artifact](../../data/evaluation-2026-11-05/t008.json).
- [Reference 1](https://aa.usno.navy.mil/faq/seasons_orbit): Axial tilt explains seasons; distance also varies during the orbit.
- [Reference 2](https://www.weather.gov/fsd/season): Earth is closest to the Sun in January, not Northern Hemisphere summer.
- Review note: AI-proposed, source-referenced; not a blind human label. 

<a id="t009"></a>
### t009

Earth’s axial tilt is the primary cause of its annual seasons.

- Draft expectation: **true**; type: causal.
- Execution: **failed**; stop reason: `provider_failure`.
- Saved sources: 1; evidence assessments: 0; final explanation units: 0.
- [Exact local run artifact](../../data/evaluation-2026-11-05/t009.json).
- [Reference 1](https://aa.usno.navy.mil/faq/seasons_orbit): Axial tilt explains seasons; distance also varies during the orbit.
- [Reference 2](https://www.weather.gov/fsd/season): Earth is closest to the Sun in January, not Northern Hemisphere summer.
- Review note: AI-proposed, source-referenced; not a blind human label. 

<a id="t010"></a>
### t010

At higher elevations, lower atmospheric pressure makes water boil at a lower temperature.

- Draft expectation: **true**; type: causal.
- Execution: **failed**; stop reason: `provider_failure`.
- Saved sources: 1; evidence assessments: 0; final explanation units: 0.
- [Exact local run artifact](../../data/evaluation-2026-11-05/t010.json).
- [Reference 1](https://extension.colostate.edu/resource/high-elevation-food-preparation-guide/): At higher elevations lower air pressure lowers the boiling point.
- Review note: AI-proposed, source-referenced; not a blind human label. 

<a id="t011"></a>
### t011

Mount Everest is Earth’s highest mountain measured above mean sea level.

- Draft expectation: **true**; type: comparison.
- Execution: **failed**; stop reason: `provider_failure`.
- Saved sources: 1; evidence assessments: 0; final explanation units: 0.
- [Exact local run artifact](../../data/evaluation-2026-11-05/t011.json).
- [Reference 1](https://oceanservice.noaa.gov/facts/highestpoint.html): Everest leads above sea level; Chimborazo leads from Earth’s center.
- Review note: AI-proposed, source-referenced; not a blind human label. The measurement is explicitly scoped. No automatic flag just because another metric exists.

<a id="t012"></a>
### t012

Mount Everest’s summit is the point on Earth’s surface farthest from Earth’s center.

- Draft expectation: **false**; type: comparison.
- Execution: **failed**; stop reason: `provider_failure`.
- Saved sources: 1; evidence assessments: 0; final explanation units: 0.
- [Exact local run artifact](../../data/evaluation-2026-11-05/t012.json).
- [Reference 1](https://oceanservice.noaa.gov/facts/highestpoint.html): Everest leads above sea level; Chimborazo leads from Earth’s center.
- [Reference 2](https://blogs.loc.gov/maps/2020/11/extremities-of-the-earth-farthest-point-from-the-center-of-the-earth/): The equatorial bulge explains why Chimborazo is farther from the center.
- Review note: AI-proposed, source-referenced; not a blind human label. Changing the measurement changes the answer.

<a id="t013"></a>
### t013

Chimborazo’s summit is farther from Earth’s center than Mount Everest’s summit.

- Draft expectation: **true**; type: comparison.
- Execution: **partial**; stop reason: `deadline_exceeded`.
- Saved sources: 2; evidence assessments: 1; final explanation units: 0.
- [Exact local run artifact](../../data/evaluation-2026-11-05/t013.json).
- Submitted notes: A poster calls Chimborazo the tallest mountain; its footnote defines height as distance from Earth’s center.
- Proposed flag: misleading_comparison/definition. The poster uses tallest while comparing distance from the center rather than elevation above sea level.
- [Reference 1](https://oceanservice.noaa.gov/facts/highestpoint.html): Everest leads above sea level; Chimborazo leads from Earth’s center.
- [Reference 2](https://blogs.loc.gov/maps/2020/11/extremities-of-the-earth-farthest-point-from-the-center-of-the-earth/): The equatorial bulge explains why Chimborazo is farther from the center.
- Review note: AI-proposed, source-referenced; not a blind human label. Check whether the context deserves a definition flag.

<a id="t014"></a>
### t014

Antarctica is a desert because it receives very little precipitation.

- Draft expectation: **true**; type: interpretive.
- Execution: **failed**; stop reason: `deadline_exceeded`.
- Saved sources: 0; evidence assessments: 0; final explanation units: 0.
- [Exact local run artifact](../../data/evaluation-2026-11-05/t014.json).
- [Reference 1](https://www.bas.ac.uk/about/education-and-schools/antarctic-factsheet/): Low precipitation makes Antarctica a desert despite its ice.
- Review note: AI-proposed, source-referenced; not a blind human label. Desert is a precipitation classification, not a temperature classification.

<a id="t015"></a>
### t015

A light-year is a unit of time.

- Draft expectation: **false**; type: interpretive.
- Execution: **failed**; stop reason: `deadline_exceeded`.
- Saved sources: 0; evidence assessments: 0; final explanation units: 0.
- [Exact local run artifact](../../data/evaluation-2026-11-05/t015.json).
- [Reference 1](https://science.nasa.gov/exoplanets/what-is-a-light-year/): A light-year measures how far light travels in a year.
- Review note: AI-proposed, source-referenced; not a blind human label. 

<a id="t016"></a>
### t016

American scientist Tim Berners-Lee invented the World Wide Web at CERN in 1989.

- Draft expectation: **almost**; type: direct_fact.
- Execution: **needs_clarification**; stop reason: `not applicable`.
- Saved sources: 0; evidence assessments: 0; final explanation units: 0.
- [Exact local run artifact](../../data/evaluation-2026-11-05/t016.json).
- Proposed correction for human review: British scientist Tim Berners-Lee invented the World Wide Web at CERN in 1989.
- [Reference 1](https://home.cern/science/computing/the-birth-of-the-web): British scientist Tim Berners-Lee invented the Web at CERN in 1989.
- Review note: AI-proposed, source-referenced; not a blind human label. Proposed Almost boundary case: invention is the core, nationality a secondary qualifier. Human reviewers must resolve the classification before acceptance scoring.

<a id="t017"></a>
### t017

The James Webb Space Telescope was launched successfully in December 2021 aboard an Ariane 4 rocket.

- Draft expectation: **almost**; type: direct_fact.
- Execution: **needs_clarification**; stop reason: `not applicable`.
- Saved sources: 0; evidence assessments: 0; final explanation units: 0.
- [Exact local run artifact](../../data/evaluation-2026-11-05/t017.json).
- Proposed correction for human review: The James Webb Space Telescope was launched successfully in December 2021 aboard an Ariane 5 rocket.
- [Reference 1](https://svs.gsfc.nasa.gov/14060): Launch occurred on 25 December 2021 aboard an Ariane 5.
- Review note: AI-proposed, source-referenced; not a blind human label. Proposed Almost boundary case: successful launch is the core and rocket designation the bounded correction. Do not pre-accept False to hide disagreement.

<a id="t018"></a>
### t018

The present-day cosmic expansion rate is approximately 73 kilometers per second per megaparsec.

- Draft expectation: **conflicting_evidence**; type: conflict.
- Execution: **partial**; stop reason: `deadline_exceeded`.
- Saved sources: 1; evidence assessments: 0; final explanation units: 0.
- [Exact local run artifact](../../data/evaluation-2026-11-05/t018.json).
- Submitted timeframe: Assess the measurement evidence available through December 31, 2024.
- Submitted definitions: Consider both local distance-ladder measurements and early-universe inferences under the standard cosmological model.
- [Reference 1](https://science.nasa.gov/mission/hubble/science/science-behind-the-discoveries/hubble-constant-and-tension/): Local and early-universe methods disagree on the expansion rate.
- Review note: AI-proposed, source-referenced; not a blind human label. Proposed conflict case; human review must assess model dependence and whether one scalar claim is sufficiently scoped.

<a id="t019"></a>
### t019

Phosphine gas was present in Venus’s clouds during the observations reported by Greaves and colleagues in 2020.

- Draft expectation: **conflicting_evidence**; type: conflict.
- Execution: **needs_clarification**; stop reason: `not applicable`.
- Saved sources: 0; evidence assessments: 0; final explanation units: 0.
- [Exact local run artifact](../../data/evaluation-2026-11-05/t019.json).
- Submitted timeframe: Evaluate the original observations using the published detection and independent reanalyses through December 31, 2021.
- [Reference 1](https://arxiv.org/abs/2009.06593): Greaves and colleagues report a phosphine signature in Venus observations.
- [Reference 2](https://arxiv.org/abs/2010.14305): Independent reanalysis disputes phosphine detection.
- Review note: AI-proposed, source-referenced; not a blind human label. Opposed analyses concern the same observations. Later measurements must not silently replace the historical question.

<a id="t020"></a>
### t020

The 1977 Wow! radio signal was produced by an extraterrestrial civilization.

- Draft expectation: **insufficient_evidence**; type: insufficient.
- Execution: **needs_clarification**; stop reason: `not applicable`.
- Saved sources: 0; evidence assessments: 0; final explanation units: 0.
- [Exact local run artifact](../../data/evaluation-2026-11-05/t020.json).
- [Reference 1](https://www.seti.org/research/seti-101/the-wow-signal): The signal’s origin remains unresolved; no repeat has established its cause.
- [Reference 2](https://seti.berkeley.edu/wow/): A targeted follow-up found no technosignature candidate; that does not identify the original cause.
- Review note: AI-proposed, source-referenced; not a blind human label. Unknown origin is not evidence of aliens and not proof against them. Avoid substituting a False verdict for lack of evidence.

## Supporting records

- [Measured results and method](results.md)
- [Machine-readable outcome summary](results.json)
- [Original proposed claim worksheet](proposed-claims.md)
- [Evaluation setup and scoring rules](README.md)
- [Demo walkthrough](demo.md)

Raw run artifacts are local and ignored by Git. Local case links resolve in this checkout; they will not be available to a remote reviewer unless the reviewed exports are shared separately. The repository report preserves aggregate results without publishing databases or private runtime configuration.
