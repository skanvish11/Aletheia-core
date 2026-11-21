# Provenance evaluation: does a source give enough basis for a verdict?

Twenty frozen claims, in ten matched pairs, that measure one failure: treating a
repeated assertion as if it were an original record. Plus two extra cases reported on
their own: a test-conditions mismatch and a contradiction that must stay False.

Results: [results.md](results.md).

## What it measures, and what it does not

Each case is a fixed packet of saved pages. The real verdict stage of the simple loop
(`SimplePipeline.judge`: the verdict call, the word-for-word quotation checks, the basis
check and the direction check) runs on those pages with the configured Nebius model.
Planning, search, page reads and the follow-up round are skipped, so both versions see
exactly the same evidence. Nothing is mocked.

**Limit:** fixed packets measure how Aletheia judges the evidence it receives. They do
not measure how often live search finds the right original record.

## Files

| File | What it holds | Sent to the model? |
| --- | --- | --- |
| `build_packets.py` | Writes the two JSON files below. Rebuilding reproduces `packets.sha256`. | no |
| `packets.json` | Per case: the claim and its saved pages (URL, title, text). | yes, through the normal verdict call |
| `answers.json` | Per case: pair, group, expected outcome, problem type, known origins, rationale. | **no**, read only by the scorer |
| `runs/baseline.jsonl`, `runs/after.jsonl` | One line per case and repeat: outcome, accepted quotations, basis decision, events. | — |
| `score.py` | Majority outcome per case, the two counts, and the 20-row table. | — |

## The cases

Seven of the ten supported claims use fictional entities with an original record in the
packet, and three use real pages saved during earlier runs (WHO, USGS, NASA). All ten
unsubstantiated claims use fictional entities. So a made-up name appears on both sides
and cannot decide the verdict, and the model's own knowledge cannot settle the supported
fictional cases.

| Pair | Supported claim's basis | Unsubstantiated claim's packet |
| --- | --- | --- |
| P01 | A lab's own battery test report | One forum anecdote, repeated as fact on two sites |
| P02 | Corvane's press release, for "Corvane advertised up to 20 hours" | The same release and three paraphrases, for "the battery lasted 20 hours in a test" |
| P03 | The benchmark maintainers' leaderboard | Three blogs citing each other in a circle |
| P04 | The race organiser's ratified results | An unofficial time repeated on three sites |
| P05 | The water authority's own annual report | A spokesperson's remark, for a claim about the report's contents |
| P06 | USGS elevation table (real) | One hiker's GPS reading, later attributed to a survey office |
| P07 | WHO malaria estimate (real) | An estimate traced only to a social-media post |
| P08 | NASA launch release (real) | One fan site's bare assertion |
| P09 | A club's own page about its mascot | Three planted pages casually saying the mascot dog is blue |
| P10 | A lab's own earbud test page | The same "lab report" copied onto three shopping sites |
| X01 | — | Video-playback record, claim about a web-browsing test |
| X02 | — | Record says 20 h 6 min; claim says 24 hours (expected False) |

## Reproduce

Needs `NEBIUS_API_KEY`. Settings used for the reported runs:

```bash
export NEBIUS_MODEL=deepseek-ai/DeepSeek-V4-Pro-0813
export ALETHEIA_PROVIDER_TIMEOUT_SECONDS=120
export ALETHEIA_MODEL_MAX_OUTPUT_TOKENS=16384
```

Baseline, on the commit before the change (`3c3e0af`), with this directory and the
script copied in:

```bash
git worktree add ../aletheia-baseline 3c3e0af
cp -r evals/provenance ../aletheia-baseline/evals/
cp scripts/evaluate_provenance.py ../aletheia-baseline/scripts/
cd ../aletheia-baseline && uv run python scripts/evaluate_provenance.py --label baseline --repeats 3
```

After the change, from this branch:

```bash
uv run python scripts/evaluate_provenance.py --label after --repeats 3
```

Score:

```bash
python evals/provenance/score.py evals/provenance/runs/baseline.jsonl evals/provenance/runs/after.jsonl
```

The model samples at its default temperature, so individual runs vary; that is why each
case runs three times and the table shows every run.
