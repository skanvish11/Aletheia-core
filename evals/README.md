# Aletheia evaluation set

Human-reviewed claims with expected decisions, used to measure whether Aletheia reaches the right decision, raises the right qualification flags, proposes a correct correction when a claim is Almost true, and cites evidence that actually supports what it says. This is the acceptance set described in the root [README](../README.md) section 12. It is evidence for the rubric's "sourced and verifiable answers" criterion, not a separate score.

**Status:** format, validator and CI checks only. The tuning claims are added in a later PR. The decision shape follows the research decision contract introduced with the research pipeline (#11).

## Layout

| Path | What it holds |
| --- | --- |
| `schema/claim.schema.json` | The record format. Decisions mirror the research decision contract; flag types and dimensions mirror README §6. |
| `validate.py` | Checks records against the schema plus the cross-field rules below. Standard library only. |
| `test_validate.py` | Tests for the validator. |
| `labels/<labeler>/<id>.json` | One labeler's blind label for one claim: a single `draft` record. |
| `claims.json` | The reconciled tuning set: an array of `reconciled` or `contested` records. |
| `examples/example-claims.json` | Four illustrative records: True with a flag, False, Almost, and unable to decide. Invented, and not part of the set. |

A file's **location** decides its kind: any JSON file under `evals/labels/` is a blind label and must sit exactly at `labels/<labeler>/<id>.json` as one draft object; every other file is an array of reconciled records. `claims.json` is required; it may be `[]`.

## The record

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | Stable ID such as `t001`. Never reused. |
| `split` | yes | Always `tuning` in this repo (see the held-out policy below). |
| `claim` | yes | The claim exactly as a user would submit it (10–500 characters). |
| `context` | no | Optional `timeframe`, `location`, `definitions`, `notes` submitted with it. |
| `case_type` | yes | `direct_fact`, `comparison`, `causal`, `interpretive`, `conflict` or `insufficient`. Used to check the set covers each kind. |
| `expected` | yes | The decision a correct run should reach (see below). |
| `acceptable_alternatives` | yes | Other decisions that also count as correct; may be empty. Must not repeat `expected` or each other. |
| `expected_flags` | yes | Flags a correct run should raise: `{type, dimension, rationale}`. May be empty. |
| `key_sources` | yes | 1–3 sources a correct run should find, each `{url, shows}`. |
| `as_of` | yes | Date (`YYYY-MM-DD`, exactly) the expected decision was checked. Evidence can change later. |
| `labelers` | yes | One name in a draft; two or more in a reconciled or contested record. |
| `status` | yes | `draft`, `reconciled` or `contested`. |
| `reviewer_note` | yes | Why this decision is expected; for `contested`, what the disagreement was. |

### The decision

Every decision, expected or alternative, has four fields:

| `outcome` | `verdict` | `unable_to_decide_reason` | `expected_correction` |
| --- | --- | --- | --- |
| `decided` | `true` or `false` | `null` | `null` |
| `decided` | `almost` | `null` | **required:** `{what_is_correct, what_needs_correction, corrected_claim}` |
| `unable_to_decide` | `null` | `insufficient_evidence` or `conflicting_evidence` | `null` |

The `expected_correction` is the labelers' reviewed expectation, so a run that says "almost" with the wrong correction can't score as correct.

Flag types are `misleading_comparison` and `narrow_scope`. Dimensions are `population`, `timeframe`, `units`, `baseline`, `condition`, `jurisdiction`, `definition`, `evaluation_setup` and `benchmark_subset`.

### Rules beyond the schema

- Decisions follow the table above: undecided means a reason and a null verdict; decided means a verdict and no reason; `almost`, and only `almost`, has an `expected_correction` with all three parts.
- `acceptable_alternatives` never repeats the expected decision, and no alternative appears twice.
- The same flag `type` + `dimension` appears at most once per record.
- `draft` has exactly one labeler; `reconciled` and `contested` have at least two.
- `claims.json` holds no drafts, and its IDs are unique.
- A label file lives exactly at `labels/<labeler>/<id>.json`, with `labelers: [<labeler>]` and `status: draft`. JSON files anywhere else under `labels/` are errors, not skipped.
- An Almost `corrected_claim` must differ from the claim (ignoring case and spacing).
- `as_of` is exactly `YYYY-MM-DD` and not in the future.
- Fields with the wrong type are reported; they never stop validation of the rest of the file.

## Labeling workflow

1. **Label blind.** Each labeler works on their own branch (`eval/labels-<name>`) and writes `labels/<name>/<id>.json` for every claim, without looking at the other labeler's files. Research each claim yourself; record the sources you relied on in `key_sources`.
2. **Commit before comparing.** Both labelers push their branches before either opens the other's. Blind labels are merged as-is, so the disagreement record stays in history.
3. **Record agreement before discussion** (see below) in the reconciliation PR.
4. **Reconcile.** Discuss every disagreement. If you agree, write one `reconciled` record into `claims.json`. If you still disagree, Pari decides, the record is `contested`, and `reviewer_note` says what the disagreement was.
5. **Validate.** `python evals/validate.py` must pass before merging.

### Choosing the decision

Work in this order: **scope the assertion, then choose the decision, then the flags.** Flags are a separate axis: any decision can carry them.

1. **Scope first.** Settle what the claim actually asserts, especially its comparator ("earlier models": which?). Don't silently narrow it to whatever reading makes the numbers work. If it can't be resolved, scope it explicitly in `claim` or `context` before labeling, or leave it out of the set.
2. **Decide:**
   - **True:** the scoped claim is supported as written.
   - **False:** its core is materially wrong. Changing a central quantity (3x when the evidence says 1.4x) is a material correction, so it is False, not Almost.
   - **Almost:** the core is substantially correct and needs one specific, bounded, evidence-backed correction. Write all three correction parts. Almost is **not** "uncertain", "close enough", numerically near, or a stand-in for conflicting evidence.
   - **Unable to decide, `insufficient_evidence`:** the available evidence can't settle it. Missing support is not contradiction, so this is not `false`.
   - **Unable to decide, `conflicting_evidence`:** credible evidence points both ways and can't be resolved. Never label this Almost.
3. **Flags** add context to the decision (a misleading baseline, a narrower scope than the wording suggests). A flag never repairs a claim that needs a correction.

`acceptable_alternatives` are for genuinely defensible readings of one specific case, explained in `reviewer_note`. Never pre-accept a second verdict for a whole category: then the eval can't catch the pipeline getting the distinction wrong.

The examples show the distinction on one product: "3x vs the 2019 X0" is True with a `misleading_comparison` flag on how it's presented; "3x vs the 2023 X1" is False; a correct battery figure with a wrong release month is Almost.

- There is no automatic mapping from the old `mixed` verdict: re-judge each case against its evidence.

### Agreement rate

Computed over the blind labels before discussion, and reported in the reconciliation PR and here:

- **Decision agreement:** share of claims where both labelers chose the same `(outcome, verdict, unable_to_decide_reason)` for `expected`.
- **Flag agreement:** share of claims where both labelers' flag sets match exactly on `{type, dimension}`.

It describes how hard the claims are; it is not a quality score for the system.

## Held-out policy

Six held-out claims are written and labeled by Pari alone and are **never committed to this repository**. Anyone who writes prompts or flag logic must not see them before the final evaluation run. Report that the held-out set has a single labeler.

## Scoring (for the eval runner)

- **Decision accuracy:** a run is correct when its `(outcome, verdict, unable_to_decide_reason)` equals `expected` or one of `acceptable_alternatives`.
- **Almost correction:** when the matched decision is `almost`, a reviewer compares the run's correction with `expected_correction`. It counts as correct only if all three parts say substantially the same thing and are cited. A matching label with a wrong correction is wrong.
- **Flag precision and recall:** per flag type, matching on `{type, dimension}` against `expected_flags`.
- **Citation support:** each cited excerpt is checked by hand for whether it supports the statement it's attached to.
- **Failures count:** every `partial` or `failed` run is scored as wrong for decision accuracy, never excluded. Report how many there were.
- Report results with and without `contested` records.

## Commands

```sh
python evals/validate.py                      # claims.json and all label files
python evals/validate.py path/to/file.json    # specific files
python -m unittest discover -s evals          # validator tests
```

CI (`.github/workflows/evals.yml`) runs all three, with the examples as the specific file, on every PR that touches `evals/`. The backend's `pytest` run doesn't collect these tests.
