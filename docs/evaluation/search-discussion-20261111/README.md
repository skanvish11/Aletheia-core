# Saved backend experiments and pilot evidence

Read **[PR #20 — Phase 1 implementation](https://github.com/skanvish11/Aletheia-core/pull/20)** alongside **[PR #21 — discussion and experiment evidence](https://github.com/skanvish11/Aletheia-core/pull/21)**. PR #20 contains the pipeline implementation; PR #21 records what was discussed and tested, including unsuccessful results and experimental candidates. Neither an archived candidate nor a favorable isolated score means it has been promoted to production.

The [discussion record](../../backend-search-discussion-20261111.md) explains the diagnosis and results. This companion package supplies the actual saved inputs, source snapshots, model requests and available responses, traces, scripts, frozen source copies, reviews, and SQLite databases behind those results.

A separate [100-claim True evaluation batch](../true-claims-100/README.md) was added to this PR after the experiment archive was frozen. It contains published FEVER `SUPPORTS` annotations for direct-claim review. It is outside the archive and has not been run through the backend.

## What is included

The [artifact archive](experiment-artifacts.tar.gz) contains **1,956 files**, approximately **150 MiB unpacked / 19.3 MiB compressed**, captured November 11, 2026 at 2:35 PM Pacific. The [manifest](manifest.json) identifies every file, its size and SHA-256 checksum, the source revision, exclusions, and package checks. The archive keeps the original workspace layout: sibling `experiments/` and `aletheia-phase-one/` directories.

| Directory inside the extracted workspace | Review entry points | Contents |
| --- | --- | --- |
| `aletheia-phase-one/data/phase-one-pilot-reviewed-20261110/` | Per-case JSON and `investigations.sqlite3` | All 30 historical pilot cases, including Python b0012, Venus b0002, SHA-256 b0011, and Paris b0026; source snapshots, saved evidence, events, and diagnostics |
| `experiments/assessment-comparison-20261110/` | `review.json`, `results.json`, `protocol.json` | Current versus simpler assessor; baseline source, scripts, requests and provider records |
| `experiments/evidence-first-comparison-20261110/` | `review.json`, `results.json` | Exact quotation extraction before explanation, including withheld-evidence controls |
| `experiments/fixed-evidence-decision-20261110/` | `review.json`, `results.json` | Fixed quotations and explicit comparison prompt |
| `experiments/fresh-model-comparison-20261110/` | `review.json`, `cases.json` | Nemotron and Qwen comparison on fresh diagnostic cases |
| `experiments/diagnostic-round-20261111/` | `summary.json`, `confirmation/review.json` | Independent selection, assessment, validation and confirmation experiments |
| `experiments/pipeline-replay-20261111/` | `analysis/results/summary.md`, `harness/README.md` | Actual pipeline replay, both frozen source arms, 24 run databases, traces, model records and failure analysis |
| `experiments/selection-hardening-20261111/` | `v3/review/final-review.json` | All three selector versions, fixtures, reviews, coverage results and the Berlin regression |
| `experiments/standard-retrieval-20261111/` | `analysis/findings.txt`, `analysis/run/summary.json`, `review/quotation-audit.json` | BM25, full-passage reranking, hybrid methods, saved sources, rankings, selected packets, and the quotation integration failure |
| `aletheia-phase-one/` outside `data/` | `pyproject.toml`, `uv.lock`, `src/`, `docs/` | Tracked source snapshot at the exact later experiment baseline `0246699a9e478b4588a38df252a0a047a4910624` |

The archive contains historical failure records as well as successful checks. The two TypeScript `tsconfig` files use comments and therefore are not strict JSON; the manifest records those parser exceptions. Original research documents retain their source URLs, and third-party source material remains attributable to its original publishers. Inclusion as evidence does not relicense that material.

## Relationship to PR 20 and the local baseline

At packaging time PR #20 ended at `c8ac904689d513501e7481b3f8f5fc40eff68bee`. The experiments used the additional local commit `0246699`, which simplified model contracts and restored bounded assessment repairs. That commit had not been pushed to PR #20.

To make the exact baseline available without changing PR #20, this package includes both the tracked source snapshot and [the single-commit patch](baseline-0246699.patch). The patch is for a clean checkout at the PR #20 revision above; inspect it before applying it. It is not applied to PR #21's main-based runtime code. Historical pilot traces and some earlier source freezes refer to their own older revisions and are preserved as such.

## Verify and inspect without provider calls

From the PR #21 repository root, run:

```sh
python3 docs/evaluation/search-discussion-20261111/verify_artifacts.py
python3 docs/evaluation/search-discussion-20261111/verify_artifacts.py --extract /tmp/aletheia-pr21-review
```

Choose a new destination for extraction. The utility verifies the archive checksum, exact inventory, every member's size and checksum, and safe paths before extracting regular files. It refuses an existing destination and does not run any archived experiment or contact a provider.

The [verification report](verification.json) records the completed checks. Both frozen arms of the extracted pipeline replay passed the existing offline harness using a local environment with backend dependencies; no provider calls were made. This verifies fixture behavior and package usability, not the historical live results or scientific validity of the experiments.

The extracted files can be inspected directly. For example, open `experiments/standard-retrieval-20261111/analysis/findings.txt` and `experiments/pipeline-replay-20261111/analysis/results/summary.md` under the extraction directory. The current package manifest is the integrity reference for distributed bytes.

## Rerun boundaries

This is a preserved experiment workspace, not a promise that every historical script is a one-command portable runner. The original protocols, source freezes, model revisions, package versions, and scripts are included unchanged. Some old manifests contain original absolute paths and source-file hashes; some runners expect a particular working directory, a local environment, Git metadata, or the original experiment's output to be absent. Do not overwrite archived results to rerun an experiment. Use a separate copy and record new results separately.

SQLite files were exported with SQLite's backup API so committed changes in WAL files are included in self-contained databases. Their logical records are preserved, but physical file checksums may differ from original historical database hashes. WAL and SHM sidecars are omitted. All 54 exported databases passed integrity checks, and their SQL dumps matched the original databases. Use the new package manifest for these exported files; do not rewrite original experiment manifests to conceal the transformation.

For dependency setup, the baseline includes its locked Python project; follow its setup instructions in a separate environment. Standard-retrieval model weights and environments are not bundled. That experiment includes `shared/model-manifest.json`, `shared/package-versions.txt`, and download/setup scripts so the exact model revisions can be identified. A fresh download requires network access.

Reading saved results and running the package verifier requires no credentials. Some archived experiment runners make paid model calls when explicitly invoked in live mode; the pipeline replay replaces web retrieval with saved data but still calls a live model in its live mode. Review each protocol and its limits before rerunning. No provider calls were made to prepare this package.

## Deliberate exclusions and known gaps

- Credential/settings files, virtual environments, downloaded model weights, caches, Python bytecode, and SQLite sidecars are excluded.
- The broader separate claim-bank inventory was an unexecuted review queue, not one of these completed backend experiments, and is excluded from the archive. The 100-claim batch linked above is a new, separate PR artifact.
- `mistake-one-focused-20261111` was still running at packaging time. Its quotation repair and separate exact-outcome/context tests remain pending in the discussion snapshot and are not presented as completed artifacts here.
- Raw responses that the original pipeline failed to record cannot be recovered by packaging. In particular, the replay's capture limitation and unavailable historical rejected responses remain explicit in the original reports.
- Frozen source coverage, citation checks, and small synthetic results do not establish production answer accuracy or fresh-search quality.

The archive and patch were scanned for credential patterns, and JSON records were checked for nonempty sensitive credential fields before publication. The original workspaces and production source were not edited during packaging.
