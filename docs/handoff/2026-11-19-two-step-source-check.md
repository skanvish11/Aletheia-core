# Plan: a separate source check after the verdict (two-step design)

Branch: `claude/eloquent-fermi-yc2kbw`. Status: **planned, not built.** This note is
meant to be enough to pick the work up cold.

## Why

Aletheia checks that a quotation is word for word on a saved page, but not whether that
page *establishes* the claim. A manufacturer's "up to 20 hours" proves the advertisement,
not a test result, and a thousand pages repeating it are still one source. On 20 frozen
test claims (`evals/provenance/`), the current `main` (`3c3e0af`) marked fake claims True
in 25 of 30 runs.

This branch tried fixing that inside the single verdict call: the model also describes
each page's basis (record, producer, original or repeated), and code withholds a true or
false verdict without a qualifying basis. It stopped the fake claims but cost real
accuracy:

| Version | Fake claims → True (of 30 runs) | Supported → True (of 30 runs) | 77 real claims correct | Right among true/false given |
| --- | ---: | ---: | ---: | ---: |
| `main` (`3c3e0af`) | 25 | 24 | 60 | 54 / 58 |
| v2: basis check in the verdict call | 0 | 26 | 37 | 30 / 32 |
| v3: + official addresses + "quote the strongest page" | 0 | 25 | 34 | 27 / 30 |
| v3 answers, loosest rule (offline re-score) | 0 | 26 | 41 | 34 / 37 |

Two causes: the code check blocked well-established facts whose pages are reputable
summaries, and the longer instructions made **the model itself** decline more often
(21 cannot settle against 14 on `main`). No code rule can win the second part back.

Details: `evals/provenance/README.md`, `evals/provenance/results.md`,
`evals/provenance/trusted-replay/README.md`.

## The idea

Keep `main`'s verdict call exactly as it was, so its accuracy on real claims comes back.
Add a **second, separate model call** that runs only when the verdict is true or false
and asks one question: *is there an actual record behind this, or only repetition?*
Withhold the verdict only when the answer is clearly no.

```
plan → search → read → verdict call (main's, unchanged) → quotation checks
     → NEW source check call (only if true/false) → code gate → direction check
```

## Steps

1. **Restore `main`'s verdict call.** In `src/aletheia/one_call.py`, bring back
   `INSTRUCTIONS` and `Answer` (`verdict`, `quotes`, `reason`) from `3c3e0af`
   (`git show 3c3e0af:src/aletheia/one_call.py`). `validate_answer` goes back to quote
   checks only. This also restores `scripts/baseline_verdict.py` to measuring the same
   call as before, so the trusted-claim numbers stay comparable.

2. **Move the basis reading into its own call.** Keep `SourceBasis`, `basis_check`,
   `provenance_on_page`, `reference_site`, `same_party` and `basis_reason`. Add:
   - `SOURCING_INSTRUCTIONS`: the basis part of the current instructions only (what
     each page offers, who produced it, original or repeated, conditions, date, passages
     word for word, "unknown" when silent). No verdict wording.
   - `Sourcing` schema: `claim_about`, `named_source`, `needs_test_conditions`,
     `sources: list[SourceBasis]`, `original_record_not_supplied`.
   - Input: the claim, the same offered pages, and which page numbers carry the accepted
     quotations. Do **not** send the verdict, so the call cannot simply agree with it.

3. **Gate on clear weakness only.** Withhold a true or false verdict when no page that
   carries an accepted quotation has *all* of: provenance passages on the page, a known
   producer and record, conditions known if the result depends on them, and one of:
   - a documented record on the producer's own site;
   - a page on an official address (`.gov`, `.edu`, `.int`, `.mil`, `.ac`), documented
     or secondhand;
   - for a claim about what a named source said, that source's own publication.
   Keep the "two different producers" route. This is the `block_clear_weak` rule that
   scored best offline (41/77 on v3 answers, with 0 fake claims through).

4. **Wire it into `SimplePipeline.judge`** (`src/aletheia/simple.py`), after the quote
   location step and before `check()`. On a withheld verdict: `cannot_settle`, the
   `basis_reason` text as the reason, the `no_qualifying_basis` event, and
   `original_record_not_supplied` passed to the follow-up planner as now.
   - Budget: `MODEL_CALLS` 6 → 8 (one more call per round), and update the comment.
   - If the source check call fails (non-fatal provider error): **withhold** the verdict
     and add the limitation "The source check could not be run." This is the opposite of
     the direction check, which fails open. Fail open instead if the team prefers
     availability; say which in the PR.
   - Bump `PROMPT_VERSION` to `one-call-v1+sourcing-v1` and `APPLICATION_VERSION`.
   - Keep `provenance_fields` filling the saved evidence's provenance fields from the
     source check.

5. **Tests.** `tests/test_provenance_basis.py` already covers the gate rules; point its
   fake answers at the `Sourcing` schema. In `tests/test_simple_pipeline.py`, the `Fake`
   provider needs a reply for the new schema title (`Sourcing`), and expected call lists
   become `[..., "Answer", "Sourcing", "Check"]`. Revert the `sourced(...)` wrappers in
   `tests/test_trusted_evaluation.py` and `tests/research_fixtures.py` once `Answer` is
   back to three fields. Add: source check fails → verdict withheld with the limitation;
   source check never runs on `cannot_settle`.

6. **Evaluate, same settings as before.**

   ```bash
   export NEBIUS_MODEL=deepseek-ai/DeepSeek-V4-Pro-0813
   export ALETHEIA_PROVIDER_TIMEOUT_SECONDS=120
   export ALETHEIA_MODEL_MAX_OUTPUT_TOKENS=16384
   ```

   20 frozen cases, 3 repeats (about 10 minutes):

   ```bash
   uv run python scripts/evaluate_provenance.py --label after-v4 --repeats 3
   python evals/provenance/score.py evals/provenance/runs/baseline.jsonl evals/provenance/runs/after-v4.jsonl
   ```

   77 trusted claims on saved pages. `scripts/baseline_verdict.py` makes only the verdict
   call, so extend it (or add a sibling script) to run the source check and gate on the
   same pages, then:

   ```bash
   uv run python scripts/baseline_verdict.py --model "$NEBIUS_MODEL" --output runs/trusted-v4
   uv run python scripts/score_trusted.py <before run> runs/trusted-v4
   ```

   The before run of the 77 is not committed (only its scores, in
   `evals/provenance/trusted-replay/`); rerun `main`'s call with
   `git worktree add ../aletheia-main 3c3e0af` if a fresh comparison is wanted. Run the
   77 twice if time allows: on `main`, two runs differed on 13 of 77 claims.

   `scripts/evaluate_provenance.py` routes through `HTTPS_PROXY` only when it is set,
   for sandboxed machines; on a normal machine nothing extra is needed.

## When to ship

Decide before looking at the numbers:

- **Ship** if fake claims → True is at most 3 of 30 runs **and** the 77 real claims
  score at least 56 correct (within run-to-run noise of `main`'s 60).
- **Report, don't ship** otherwise, with the numbers, and say which of the two goals
  failed.

Either way, open the PR with the 20-row table, the 77-claim score, the cost (one more
model call per decided claim), and the limit: fixed pages measure how Aletheia judges
what it reads, not how often search finds the original record.

## After that

- Update `README.md` → "What counts as evidence" (it currently describes the v2 rule and
  its numbers) and "Accuracy".
- Update `docs/simple-loop.md` → "The basis check".
- The staged pipeline (`sufficient` in `src/aletheia/verdicts.py`) is unchanged and not
  measured; leave it for a separate change.
- Known gaps, unchanged by this plan: quotations from Markdown tables can fail word-for-
  word matching (case S06); a test-conditions mismatch can return False instead of
  cannot settle (case X01).
