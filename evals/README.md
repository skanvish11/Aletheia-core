# Aletheia evaluation set

Human-reviewed claims with expected outcomes, used to measure whether Aletheia reaches the right verdict, raises the right qualification flags, and cites evidence that actually supports what it says. This is the acceptance set described in the root [README](../README.md) section 12. It is evidence for the rubric's "sourced and verifiable answers" criterion, not a separate score.

**Status:** format and validator only. The tuning claims are added in a later PR.

## Layout

| Path | What it holds |
| --- | --- |
| `schema/claim.schema.json` | The record format. Verdicts, flag types and dimensions mirror README §6. |
| `validate.py` | Checks records against the schema plus the cross-field rules below. Standard library only. |
| `test_validate.py` | Tests for the validator. |
| `labels/<labeler>/<id>.json` | One labeler's blind label for one claim (`status: draft`). |
| `claims.json` | The reconciled tuning set: an array of `reconciled` or `contested` records. |
| `examples/example-claims.json` | One illustrative record. Invented, and not part of the set. |

## The record

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | Stable ID such as `t001`. Never reused. |
| `split` | yes | Always `tuning` in this repo (see the held-out policy below). |
| `claim` | yes | The claim exactly as a user would submit it (10–500 characters). |
| `context` | no | Optional `timeframe`, `location`, `definitions`, `notes` submitted with it. |
| `case_type` | yes | `direct_fact`, `comparison`, `causal`, `interpretive`, `conflict` or `insufficient`. Used to check the set covers each kind. |
| `expected_verdict` | yes | `supported`, `contradicted`, `mixed` or `insufficient_evidence`. |
| `acceptable_verdicts` | yes | Other verdicts that also count as correct; may be empty. Must not repeat `expected_verdict`. |
| `expected_flags` | yes | Flags a correct run should raise: `{type, dimension, rationale}`. May be empty. |
| `key_sources` | yes | 1–3 sources a correct run should find, each `{url, shows}`. |
| `as_of` | yes | Date the expected outcome was checked. Evidence can change later. |
| `labelers` | yes | One name in a draft; two or more in a reconciled or contested record. |
| `status` | yes | `draft`, `reconciled` or `contested`. |
| `reviewer_note` | yes | Why this outcome is expected; for `contested`, what the disagreement was. |

Flag types are `misleading_comparison` and `narrow_scope`. Dimensions are `population`, `timeframe`, `units`, `baseline`, `condition`, `jurisdiction`, `definition`, `evaluation_setup` and `benchmark_subset`.

### Rules beyond the schema

- `acceptable_verdicts` never repeats `expected_verdict`.
- The same flag `type` + `dimension` appears at most once per record.
- `draft` has exactly one labeler; `reconciled` and `contested` have at least two.
- `claims.json` holds no drafts, and its IDs are unique.
- A label file lives at `labels/<labeler>/<id>.json`, with `labelers: [<labeler>]` and `status: draft`.
- `as_of` is not in the future.

## Labeling workflow

1. **Label blind.** Each labeler works on their own branch (`eval/labels-<name>`) and writes `labels/<name>/<id>.json` for every claim, without looking at the other labeler's files. Research each claim yourself; record the sources you relied on in `key_sources`.
2. **Commit before comparing.** Both labelers push their branches before either opens the other's. Blind labels are merged as-is, so the disagreement record stays in history.
3. **Record agreement before discussion** (see below) in the reconciliation PR.
4. **Reconcile.** Discuss every disagreement. If you agree, write one `reconciled` record into `claims.json`. If you still disagree, Pari decides, the record is `contested`, and `reviewer_note` says what the disagreement was.
5. **Validate.** `python evals/validate.py` must pass before merging.

### Agreement rate

Computed over the blind labels before discussion, and reported in the reconciliation PR and here:

- **Verdict agreement:** share of claims where both labelers chose the same `expected_verdict`.
- **Flag agreement:** share of claims where both labelers' flag sets match exactly on `{type, dimension}`.

It describes how hard the claims are; it is not a quality score for the system.

## Held-out policy

Six held-out claims are written and labeled by Pari alone and are **never committed to this repository**. Anyone who writes prompts or flag logic must not see them before the final evaluation run. Report that the held-out set has a single labeler.

## Scoring (for the eval runner)

- **Verdict accuracy:** a run is correct when its overall verdict equals `expected_verdict` or is in `acceptable_verdicts`.
- **Flag precision and recall:** per flag type, matching on `{type, dimension}` against `expected_flags`.
- **Citation support:** each cited excerpt is checked by hand for whether it supports the statement it's attached to.
- **Failures count:** every `partial` or `failed` run is scored as wrong for verdict accuracy, never excluded. Report how many there were.
- Report results with and without `contested` records.

## Commands

```sh
python evals/validate.py                      # claims.json and all label files
python evals/validate.py path/to/file.json    # specific files
python -m unittest discover -s evals          # validator tests
```
