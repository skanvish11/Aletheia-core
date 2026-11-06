# Step 7: evaluation and demo

This work adds a proposed 20-case tuning set and an explicitly enabled live runner.
It does not certify research quality. The candidate answers are AI proposals;
human labeling, passage review, and the private held-out evaluation remain required.

- [Findings, all 20 outcomes, and proposed fix order](review-and-fix-plan.md)
- [First repairs, all seven follow-up attempts, and remaining failures](repairs.md)
- [Adversarial review: before/fix/open-gap comparison and trace guide](adversarial-review.md)
- [Proposed claims and references](proposed-claims.md)
- [Machine-readable proposals](proposed-claims.json)
- [Results and limitations](results.md)
- [Demo walkthrough](demo.md)

## Setup and offline checks

From the repository root, install Python 3.12+ and uv, then run:

```sh
uv sync --locked --dev
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest
uv run --locked python scripts/evaluate_research.py \
  --cases docs/evaluation/proposed-claims.json
```

The last command validates the proposed records without loading dotenv or calling
providers. Empty datasets, duplicate IDs/requests, malformed decisions, and invented
review status are rejected. The ordinary test suite remains offline.

## Run real research

Configure `NEBIUS_API_KEY`, `TAVILY_API_KEY`, and an explicit `NEBIUS_MODEL` through
the runtime environment or an existing runtime settings file. Never display or
commit that file. `--dotenv /absolute/path/to/settings` loads it only at runtime;
`--model` optionally selects a model explicitly without a silent fallback.

Start with one case:

```sh
uv run --locked python scripts/evaluate_research.py \
  --cases docs/evaluation/proposed-claims.json \
  --live --limit 1 --output data/evaluation-pilot
```

Run the proposed set and one explicit refresh:

```sh
uv run --locked python scripts/evaluate_research.py \
  --cases docs/evaluation/proposed-claims.json \
  --live --limit 20 --refresh-first --output data/evaluation-full
```

These commands make paid calls. Each investigation uses the application's existing
time/call limits, including retries. The runner is sequential, accepts at most 20
cases per invocation, and adds at most one refresh when requested. At the deep
profile, a run permits at most 16 model attempts, 8 searches, and 10 extraction
units within 240 seconds. The runner waits up to 260 seconds for a terminal state.
No price estimate is substituted for actual billing. Account/configuration errors
stop the batch; unrun cases remain visible in the report.

The output directory must be new. Previous reports are never overwritten, and each
batch has a fresh database so saved reuse cannot masquerade as fresh evaluation.
Do not rerun to select the most favorable answer: keep all attempts and explain
why any repeat was necessary.

## Artifacts and scoring

Each case gets a JSON artifact with the saved result, evidence, progress events,
comparison, elapsed time, and safe network metadata. No credentials, request bodies,
raw model responses, or private reasoning are exported. The local SQLite database
retains source snapshots for inspection. All run artifacts stay under ignored
`data/`; review exports before sharing or publishing.

`manifest.json` identifies the backend revision, whether the checkout was modified,
model/configuration, dataset hash, timestamps, and restart checks. `cases.json`
freezes the submitted set. `scores.json` and `summary.json` update after each case,
so earlier outcomes survive a later failure. Newer runner diagnostics also preserve
safe budget-attempt outcome codes when a failed run has no final result.

Scoring follows PR #7's decision contract:

- Compare outcome, verdict, and undecided reason separately. Insufficient evidence
  and conflicting evidence cannot match each other.
- Every partial, failed, clarification, or runner-failed case counts as wrong in
  the attempted-case denominator. Unrun cases are separately reported; an interrupted
  batch is not a full-set result.
- A matching Almost label remains pending until a human checks all three correction
  parts and their citations. Bounds show the effect of pending corrections; they
  are not a claim of verified accuracy.
- Count flag precision/recall by type and dimension. Undefined ratios are null,
  not perfect scores. A set with one expected flag cannot establish flag quality.
- Report all records and a separate view excluding contested records.
- Human citation support remains pending even when labels match. The runner does
  not auto-certify human review, acceptance completion, or a held-out result.

The runner sends only `claim` and `context` to the research API. Expected answers,
reference sources, flags, and reviewer notes never enter application prompts.

## Relationship to PR #7

PR #7 supplies the separate human-labeling schema and validator. The proposal lives
under `docs/evaluation/`, not `evals/claims.json`, because it has `status: proposed`
and no human labelers. Once independently reviewed and reconciled, its fields align
with the PR #7 record format and the runner accepts `reconciled`/`contested` records.
The runner's input checks do not replace that PR's labeling validator or workflow.
No held-out data has been requested, read, or created by this work.

## Completion gates

Step 7 is complete only after the team reviews the expected answers and every
returned citation, assesses the whole acceptance set including failures, documents
weaknesses, and demonstrates real normal, insufficient, saved, and refresh paths.
A script, a candidate dataset, or passing offline tests alone does not meet that gate.
