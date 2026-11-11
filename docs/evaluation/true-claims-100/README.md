# One hundred true claim candidates for Phase 1

This is the first 100-claim True batch requested for Aletheia's direct-fact and direct-comparison evaluation. [Read the numbered claims](claims.md) or the [machine-readable records](claims.json). Each statement retains the source benchmark's `SUPPORTS` label and original evidence-set pointers. The selected set spans history, geography, public institutions, science, technology, sport, and culture.

## What the label establishes

[FEVER](https://fever.ai/dataset/fever.html) contains human-annotated supported, refuted, and not-enough-information claims. For supported claims, its annotators identified evidence sentences in a June 2017 English Wikipedia corpus. All 100 records here are labeled `SUPPORTS` and `VERIFIABLE` in the publisher's development file. The list uses FEVER claim wording verbatim; it is a published, source-annotated starting batch.

The `evidence_sentence_pointers` and `original_evidence_sets` fields preserve the publisher's evidence references. The article URLs are convenient current-page links; they do not retrieve the archived 2017 sentence text. The publisher's labels have not been independently reconciled against Aletheia's True/False/Almost definitions, and no claim has been rechecked against the current web. `claims.json` records these limitations on every claim. This pack is development material, not a private held-out set or an acceptance result.

The chosen claims were screened for being specific, predominantly stable and plausibly within the direct-research scope. That screening is an authoring step, not a second independent factual label. The 100 should be reviewed individually for direct-method eligibility, exact scope, source quality and current correctness before being treated as Aletheia gold labels or submitted as a scored live batch. If a claim is rejected, preserve its ID and reason, then choose a replacement from a distinct fact family.

## How to use the pack

1. Have two reviewers independently inspect the original assertion and its material details. Read the cited historical evidence and a suitable current or archival source. Record exact supporting passages, source dates and any limitations. Reconcile disagreements before scoring.
2. Keep claim families together. Mark approved claims as development; prepare a fresh, independently held final set later. The existing 30 historical pilot claims remain separate.
3. For the backend, submit only `claim` and neutral `context` from each record. Never send `published_label`, `expected_verdict`, evidence pointers or reviewer fields to the model.
4. Start with a bounded reviewed pilot. Preserve all attempts, failures, citations, code revision, model configuration, timing and actual usage. Report False calls on these True claims as false accusations, and inspect their evidence.

No provider calls or live backend runs were made to produce this pack. It is not wired into the old `evals/claims.json` human-labeling contract, which requires two local reviewers before a reconciled record can be added.

## Provenance and reproduction

The [manifest](manifest.json) gives the source checksum and output checksum. `selected-ids.txt` freezes the 100 source record IDs. To reproduce the files, download `shared_task_dev.jsonl` from [the publisher's archive](https://zenodo.org/records/4925954) and run `python3 build.py /path/to/shared_task_dev.jsonl`. The script verifies the full source SHA-256, count, uniqueness, published labels and evidence pointers before writing the list.

Attribution: James Thorne, Andreas Vlachos, Christos Christodoulopoulos and Arpit Mittal, *FEVER: a Large-scale Dataset for Fact Extraction and VERification*, NAACL-HLT, 2018. The data annotations incorporate Wikipedia material; preserve the applicable terms described in the [FEVER license](https://fever.ai/download/fever/license.html) when reusing this pack. The added selection and metadata do not change the source claims or their original labels.
