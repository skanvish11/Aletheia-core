# Foundation performance baseline

This is a historical measurement of the revisions listed below. PR #8 review fixes
subsequently changed request-size/database guards and the benchmark's connection
cleanup and server startup. The small post-fix checks validate correctness and cleanup;
they do not update these latency measurements or establish a new performance result.

## Decision

Keep the current backend design and implementation. No application cache, flat-array rewrite, packed IDs, or connection-pool redesign was added. The proposed fingerprint/serialization change showed mixed results across workloads and database sizes, so it remains an unapplied experiment. The measurements do not justify a larger optimization project before provider integration.

## Method

Measured at 2026-11-05T01:53:43.110956+00:00 on macOS 25.6.0 / arm64, Python 3.12.14, SQLite 3.53.4.

- Baseline: commit `9b60b9204cd6482d5f075802daaddcb820c74c72`.
- Candidate: the same source with request fingerprint and context JSON prepared once before the write transaction. The exact [unapplied patch](fingerprint-candidate.patch) is included.
- Real localhost HTTP, one Uvicorn server process per variant/size/repetition, HTTPX keepalive connections, no proxies or provider calls. The child verifies the SHA-256 of the loaded source against the requested variant.
- 100, 1,000, and 10,000 seeded terminal investigations; short synthetic claims and context, null results, two events per seeded record. No real data or dotenv files are read.
- Four repetitions per size/variant, with baseline/candidate ordering reversed on alternate repetitions. Identical deterministic workloads for both variants.
- Each of five scenarios has 16 unmeasured warm-up requests and 120 measured requests per repetition: 14,400 measured requests total, plus 1,920 warm-up requests.
- Sequential reads, sequential saved duplicates, and sequential new submissions; concurrent scenarios use closed-loop batches of eight. Each identical batch uses a fresh claim, so it tests racing creation rather than merely looking up an old record.
- Seeding, startup, and integrity inspection are excluded from request timings. Database size grows during write scenarios; every run records its actual starting row count.
- Latency measures request dispatch through receipt of the HTTP response. Throughput includes client validation and batch coordination. p50 is the median; p95 is the nearest-rank 95th percentile pooled over four repetitions.
- SQLite and operating-system caches operate normally. This is a warmed local-desktop measurement, not a cold-disk benchmark or an open-loop load/capacity test.
- Correctness assertions check status codes, original claim/context, stable IDs/timestamps, reuse, exactly one creation per identical batch, row/event counts, foreign keys, and SQLite integrity. Any failure aborts the run; a successful report is emitted only after every check passes.

## Baseline results

Each cell is **median / p95**, in milliseconds.

| Operation | 100 saved | 1,000 saved | 10,000 saved |
| --- | ---: | ---: | ---: |
| Retrieve saved record | 1.37 / 1.98 | 1.37 / 1.77 | 1.36 / 1.84 |
| Resubmit saved claim | 1.55 / 3.35 | 1.47 / 1.77 | 1.51 / 2.66 |
| Submit new claim | 2.03 / 3.03 | 1.97 / 2.80 | 1.96 / 2.46 |
| 8 simultaneous identical submissions | 8.22 / 11.60 | 7.87 / 10.40 | 8.32 / 13.34 |
| 8 simultaneous distinct submissions | 9.14 / 17.91 | 8.93 / 16.65 | 9.79 / 27.04 |

Typical sequential timings remained similar as saved history increased. The slowest tested workload was simultaneous distinct writes. Its 10,000-record pooled p95 was 27.04 ms, with per-repetition p95 ranging from 17.17 to 47.79 ms. Tail variation is visible; these results do not establish a monotonic database-size bottleneck.

## Candidate comparison at 10,000 saved records

| Operation | Baseline median / p95 (ms) | Candidate median / p95 (ms) | Baseline req/s | Candidate req/s |
| --- | ---: | ---: | ---: | ---: |
| Retrieve saved record | 1.36 / 1.84 | 1.34 / 1.63 | 582.3 | 686.1 |
| Resubmit saved claim | 1.51 / 2.66 | 1.47 / 1.78 | 555.3 | 624.6 |
| Submit new claim | 1.96 / 2.46 | 1.94 / 2.41 | 461.2 | 467.4 |
| 8 simultaneous identical submissions | 8.32 / 13.34 | 7.88 / 10.13 | 613.2 | 680.2 |
| 8 simultaneous distinct submissions | 9.79 / 27.04 | 9.06 / 18.18 | 341.7 | 415.5 |

The candidate looks better in several pooled 10,000-record measurements, but that is insufficient to claim a dependable gain. At 1,000 records, concurrent distinct-write p95 increased from 16.65 to 19.30 ms and throughput fell from 466.1 to 369.2 req/s. The unchanged GET path also moved between variants, indicating environmental variation. For 10,000-record sequential new submissions, medians were almost identical (1.96 vs 1.94 ms).

**Outcome:** no demonstrated consistent improvement, so the production fingerprint implementation is unchanged. Both baseline and candidate preserve the existing design; no application cache was introduced.

## Correctness and limits

All benchmark response/integrity assertions passed, with zero observed HTTP errors. The candidate separately passed the 57-test offline correctness suite. The baseline implementation was not modified.

This tests small metadata records and up to eight concurrent client requests on one desktop. It does not measure research latency, large evidence text, long event histories, high sustained external traffic, or production hardware. No service-level latency target was specified, so this is evidence for prioritization rather than a guaranteed performance threshold. No detailed lock/connection profiler was added because this bounded workload did not identify a problem requiring a structural rewrite.

An initial three-repetition exploratory run validated the harness and exposed timing variability; the retained comparison is the subsequent four-repetition confirmation run, with no concurrent test-suite execution. No further trials were selected to favor either variant.

Full per-repetition metrics, actual starting row counts, dependency versions, source fingerprints, and pooled results are in [foundation-comparison.json](foundation-comparison.json).

## Reproduce

For a current-source baseline (no production database touched):

```sh
uv run --locked python scripts/benchmark_foundation.py --repetitions 4 --output benchmark-results.json
```

To reproduce this comparison, create two temporary copies of the baseline source, then apply the saved candidate patch only in the candidate directory:

```sh
baseline_dir=$(mktemp -d)
candidate_dir=$(mktemp -d)
git archive 9b60b92 src | tar -x -C "$baseline_dir"
git archive 9b60b92 src | tar -x -C "$candidate_dir"
patch -d "$candidate_dir" -p1 < docs/benchmarks/fingerprint-candidate.patch
uv run --locked python scripts/benchmark_foundation.py --repetitions 4 \
  --variant "baseline=$baseline_dir/src" --variant "candidate=$candidate_dir/src" \
  --output benchmark-comparison.json
```

Temporary benchmark databases and server processes are removed automatically. SQLite connections close explicitly, and the child keeps its chosen localhost socket open from binding through serving. The two source copies made in the reproduction example can be removed after inspection. Keep timing runs separate from tests and other heavy work. Full timing runs are opt-in; CI runs only a small correctness/cleanup check on Linux and Windows, without a latency gate.
