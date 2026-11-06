# Step 7 results — November 5, 2026

**The implementation is not ready for a successful live research demo.** The evaluation tooling and proposed set are in place, but the live runs expose failures. Human labeling and citation review remain outstanding.

Baseline recorded: **20/20** cases. Statuses: **13 failed, 2 partial, 5 needs_clarification**. **0 completed successfully.** These are execution outcomes against proposed cases, not a human-verified accuracy score.

## Method

- Backend: `5d4c1586736d808516dd1033b1118728bcf4ca06` (Step 4). Evaluation files were local additions; production prompts and budgets were unchanged.
- Model: `nvidia/Nemotron-3_5-Lightning`; structured JSON mode; 4,096 output tokens; 45-second provider timeout; up to two retries under the shared application budget.
- Dataset SHA-256: `0017e73af9dc81e78afe6035217e94bbd0a58c1caa2b143ae85d4f229a5978fa`. All 20 cases are tuning proposals with no human labelers. Expected answers and source references were withheld from the application.
- Each case starts fresh in one new batch database. One explicit refresh of the first case is reported separately. No failures were discarded.
- Baseline measured network attempts, including that refresh: **118**. Billed cost is unknown; no dollar estimate or success-only usage total is substituted.
- A prior single-claim smoke pilot failed. One diagnostic repeat at 4,096 tokens and one separate trial at 8,192 tokens with a refresh are also retained. Those exploratory repeats do not replace baseline results.

## Per-case baseline

| Case | Proposed decision | Observed status | Observed decision | Last research stage |
| --- | --- | --- | --- | --- |
| t001 | true | failed | No result | verifying |
| t002 | false | failed | No result | verifying |
| t003 | true | failed | No result | verifying |
| t004 | true | failed | No result | verifying |
| t005 | false | needs_clarification | No result | interpreting |
| t006 | false | failed | No result | verifying |
| t007 | true | failed | No result | verifying |
| t008 | false | failed | No result | verifying |
| t009 | true | failed | No result | verifying |
| t010 | true | failed | No result | verifying |
| t011 | true | failed | No result | verifying |
| t012 | false | failed | No result | verifying |
| t013 | true | partial | insufficient_evidence | synthesizing |
| t014 | true | failed | No result | interpreting |
| t015 | false | failed | No result | interpreting |
| t016 | almost | needs_clarification | No result | interpreting |
| t017 | almost | needs_clarification | No result | interpreting |
| t018 | conflicting_evidence | partial | insufficient_evidence | synthesizing |
| t019 | conflicting_evidence | needs_clarification | No result | interpreting |
| t020 | insufficient_evidence | needs_clarification | No result | interpreting |

See [the claim worksheet](proposed-claims.md) for wording, scope, and reference links.

## Confirmed findings

1. **Response truncation:** the 4,096-token diagnostic completed interpretation, planning, search, and extraction with HTTP 200 responses, then the evidence-assessment call ended with the safe code `truncated_output`. This distinguishes a cut-off model response from a Tavily retrieval failure. The baseline artifacts do not retain safe internal failure codes for every case, so do not assume every baseline failure has exactly this cause.
2. **More output allowance is insufficient by itself:** the separate 8,192-token Apollo trial reached synthesis after multiple research rounds, then failed with `truncated_output`. Its refresh also failed with `truncated_output` during assessment. Neither yielded a final answer. This is one exploratory trial, not a controlled model/configuration benchmark.
3. **Retrieval and passage selection need work:** agent inspection of that trial found five evidence records, including a Wikipedia navigation link classified as irrelevant. Other retrieved pages were secondary reporting or shared-origin material. No final citation-support score can be assigned because the trial published no final explanation. This is agent inspection, not human review.
4. **Unnecessary clarification:** `t005`, the Einstein Nobel claim, received a question that restated the original claim. The claim was sufficiently explicit for this proposed evaluation; the clarification is counted as unsuccessful, not excluded.

5. **Timeout and incomplete coverage:** baseline `t013` returned a partial insufficient-evidence result after model timeouts and the research deadline. Its limitations reported navigation/heading-only passages. It supplied no final explanation citations. This is an execution failure for acceptance scoring, even though the abstention avoids inventing an answer.

6. **Early latency failures:** `t014` and `t015` exhausted the research deadline during interpretation, before searching. These must not be described as citation or factual-accuracy errors; they are failed executions.

7. **Almost boundary cases remain proposals:** `t016` asked whether Berners-Lee is American and `t017` asked which Ariane rocket launched Webb. These factual questions were not researched to a final decision. Human reviewers still need to resolve whether the proposed Almost labels and single-claim scope are appropriate; no alternatives were retroactively added to make these runs pass.

## Reliability checks

- Saved response and exact resubmission identical: **20/20** recorded baseline cases.
- Saved reads and resubmission made zero provider calls: **20/20** recorded baseline cases.
- Persisted events remained ordered: **20/20** recorded baseline cases.
- Replayed events after the cursor matched the saved suffix: **20/20** recorded baseline cases.
- Read-only restart retained identical saved responses: **20/20** checked; provider-call count unchanged: **True**.
- Baseline refresh outcome: **failed**. It did create a separate version; retries reused that version, the original remained unchanged, and retry/read operations made no additional provider calls.

These checks can pass for failed investigations. They do not demonstrate a successful refreshed factual result or a meaningful evidence comparison. The progress check replays terminal events over the API; browser reconnection behavior was not tested here.

## Offline validation

- `uv sync --locked --dev` completed using the existing offline dependency cache on Python 3.15.2.
- `uv run --locked pytest`: **307 passed**. Coverage includes no expected-label leakage, failure-inclusive scoring, pending Almost review, normalized duplicate rejection, safe diagnostics, and live-call opt-in.
- Ruff lint, format, and `git diff --check`: passed.
- `scripts/smoke_foundation.py`: passed real localhost submission/reuse and persistence across a new server process. The initial sandboxed server attempt could not start; the permitted localhost rerun passed.
- Python 3.12/3.13 remote CI, a live frontend walkthrough, and independent human research review were not performed.

## Remaining work before calling Step 7 complete

1. Bound and simplify assessment/synthesis responses, then rerun the failed cases under a documented configuration. Do not merely increase token limits and assume success.
2. Improve selection of authoritative pages and useful source passages. Verify that follow-up searches address the remaining evidence gap.
3. Prevent interpretation from turning a clear factual assertion into a restatement question.
4. Obtain independent human expected labels, resolve the proposed Almost/conflict boundaries, and review returned citations once runs produce answers. Preserve the original proposal and all failed baseline results.
5. Demonstrate actual normal and insufficient-evidence results, successful refresh/comparison, and the browser integration. The current artifacts are useful failure demonstrations, not the promised successful demo.
6. Run the separately maintained held-out set under its agreed policy. It was not exposed to this work.

## Local artifacts

- Baseline: `data/evaluation-2026-11-05/`
- Diagnostic: `data/evaluation-diagnostic-2026-11-05/`
- Larger-output trial: `data/evaluation-8192-trial-2026-11-05/`
- Initial smoke pilot: `/private/tmp/aletheia-step7-pilot.json`

The data directories are ignored by Git. Each contains public case artifacts and a local database; inspect exports before sharing. The aggregate report, proposed set, evaluation tooling, tests, and walkthrough are repository deliverables; raw run artifacts remain local. The [demo walkthrough](demo.md) documents how to present live or recorded behavior honestly.
