# Replay of the 77 trusted tuning claims, before and after the basis check

One verdict call per claim on the pages saved during earlier runs (`evals/evidence`),
through `scripts/baseline_verdict.py`, model `deepseek-ai/DeepSeek-V4-Pro-0813`. Before:
commit `3c3e0af`. After: this branch. One run each, so individual claims can differ by
chance.

| | Before | After |
| --- | ---: | ---: |
| Correct of 77 (cannot settle counts when that is the label) | 60 | 37 |
| True or false answers given | 58 | 32 |
| Right among those | 54 | 30 |

Of the 28 claims that went from a true or false answer to cannot settle, the basis check
withheld 22, the model declined 5 and a quotation check failed 1 (`verdicts.csv`). Most
are well-established reference facts (history, standards, official statistics) whose
pages are reputable summaries rather than the producer's own record. The basis check
treats every such page as a secondhand report of one source, so none qualifies.

**This is a regression the change must not ship with.** See the pull request for the
options.

## Later versions

| Version | Correct of 77 | True/false given | Right among those |
| --- | ---: | ---: | ---: |
| Before (`3c3e0af`) | 60 | 58 | 54 |
| v2: strict basis check | 37 | 32 | 30 |
| v3: + official addresses (`.gov`, `.edu`, `.int`…) + "quote the strongest page" | 34 | 30 | 27 |

Re-scoring the v3 answers offline under looser rules reached at most 41. In v3 the
model itself also declines more often (21 cannot settle, against 14 before), so part of
the loss comes from the stricter instructions, not only the code check. The strict
versions did not raise the share of right answers among true/false answers on these
real claims (93% before, 90% in v3). The frozen cases (`../results.md`) show the
opposite picture: fake claims marked True fell from 25 of 30 runs to 0.
