"""Score two runs of the frozen provenance packets and write results.md.

    python evals/provenance/score.py runs/baseline.jsonl runs/after.jsonl

A case's outcome is the most common outcome over its repeats (ties shown as "split").
Counts are raw; with 10 cases per group they are not accuracy estimates.
"""

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
SHORT = {
    "true": "True",
    "false": "False",
    "insufficient_evidence": "Insufficient",
    "execution_failure": "Execution failure",
}


def load(path):
    lines = [json.loads(line) for line in Path(path).read_text().splitlines()]
    meta, runs = lines[0]["meta"], lines[1:]
    by_case = {}
    for run in runs:
        by_case.setdefault(run["id"], []).append(run)
    return meta, by_case


def majority(runs):
    counts = Counter(r["outcome"] for r in runs).most_common()
    if len(counts) > 1 and counts[0][1] == counts[1][1]:
        return "split"
    return counts[0][0]


def spread(runs):
    return "/".join(SHORT[r["outcome"]][0] for r in runs)


def decisive(runs, outcome):
    """A short note on the evidence or rule behind the majority outcome."""
    run = next((r for r in runs if r["outcome"] == outcome), runs[0])
    if run["outcome"] == "execution_failure":
        return f"error: {run.get('error')}"
    basis = run.get("basis") or {}
    if basis.get("route") and run["outcome"] in {"true", "false"}:
        urls = {q["page"]: q["url"] for q in run["accepted_quotes"]}
        pages = ", ".join(urls.get(p, f"page {p}").split("/")[2] for p in basis["pages"])
        return f"{basis['route']}: {pages or ', '.join(basis['producers'])}"
    if run["outcome"] in {"true", "false"}:
        hosts = sorted({q["url"].split("/")[2] for q in run["accepted_quotes"]})
        return "quoted " + ", ".join(hosts)
    if any(e.get("reason") == "quotations_point_the_other_way" for e in run["events"]):
        return "verdict withdrawn by the direction check"
    if any(e.get("reason") == "no_qualifying_basis" for e in run["events"]):
        why = sorted({n.get("why", n["credit"]) for n in basis.get("notes", [])})
        return "withheld: no qualifying basis (" + ", ".join(why or ["no source readings"]) + ")"
    return run["reason"][:110]


def withheld_rows(runs):
    rows = []
    for prefix, group in (("S", "Supported"), ("U", "Unsubstantiated")):
        tally = Counter()
        for cid, items in runs.items():
            if not cid.startswith(prefix):
                continue
            for run in items:
                if run["outcome"] == "true" or run["outcome"] == "execution_failure":
                    continue
                reasons = {e.get("reason") for e in run["events"]}
                if "no_qualifying_basis" in reasons:
                    tally["code"] += 1
                elif "quotations_point_the_other_way" in reasons:
                    tally["direction"] += 1
                elif run["model_verdict"] == "cannot_settle":
                    tally["model"] += 1
                else:
                    tally["quotes"] += 1
        rows.append(
            f"| {group} | {tally['model']} | {tally['code']} | {tally['direction']} "
            f"| {tally['quotes']} |"
        )
    return rows


def main(before_path, after_path):
    answers = {a["id"]: a for a in json.loads((HERE / "answers.json").read_text())}
    packets = {p["id"]: p for p in json.loads((HERE / "packets.json").read_text())}
    before_meta, before = load(before_path)
    after_meta, after = load(after_path)
    assert before_meta["packets_sha256"] == after_meta["packets_sha256"]
    assert before_meta["model"] == after_meta["model"]
    rows, counts = [], Counter()
    for cid, answer in answers.items():
        b, a = majority(before[cid]), majority(after[cid])
        group = answer["group"]
        if answer["pair"] != "extra":
            counts[(group, "before", b)] += 1
            counts[(group, "after", a)] += 1
            counts[(group, "before_runs_true")] += sum(r["outcome"] == "true" for r in before[cid])
            counts[(group, "after_runs_true")] += sum(r["outcome"] == "true" for r in after[cid])
        expected = SHORT[answer["expected"]]
        status = (
            "fixed"
            if b != answer["expected"] and a == answer["expected"]
            else "regressed"
            if b == answer["expected"] and a != answer["expected"]
            else "correct"
            if a == answer["expected"]
            else "still wrong"
        )
        rows.append(
            f"| {cid} | {answer['problem_type']} | {packets[cid]['claim']} | {expected} | "
            f"{SHORT.get(b, b)} ({spread(before[cid])}) | {SHORT.get(a, a)} ({spread(after[cid])}) "
            f"| {status} | {decisive(after[cid], a)} |"
        )
    n = len(next(iter(after.values())))
    lines = [
        "# Provenance evaluation results",
        "",
        f"Packets: `packets.json` (sha256 `{after_meta['packets_sha256'][:16]}…`), "
        f"{n} repeats per case, model `{after_meta['model']}`, "
        f"max output tokens {after_meta['max_output_tokens']}, "
        f"provider timeout {after_meta['timeout_seconds']:.0f} s.",
        "",
        f"- Before: commit `{before_meta['commit'][:10]}`, "
        f"prompt `{before_meta['prompt_version']}`",
        f"- After: prompt `{after_meta['prompt_version']}`, run from a working tree on top of "
        f"`{after_meta['commit'][:10]}` holding this branch's fix (the run file records "
        "that commit)",
        f"- Stages: {after_meta['stages']}. Nothing is mocked.",
        "",
        "A case's outcome is the majority over its repeats; the letters in brackets are the "
        "individual runs (T = True, F = False, I = Insufficient evidence, E = execution "
        "failure). The simple loop has no conflict or clarification outcome, so none "
        "appears.",
        "",
        "## The two questions",
        "",
        "| | Before | After |",
        "| --- | --- | --- |",
        f"| Unsubstantiated claims (of 10) that received True | "
        f"{counts[('unsubstantiated', 'before', 'true')]} | "
        f"{counts[('unsubstantiated', 'after', 'true')]} |",
        f"| Supported claims (of 10) that correctly received True | "
        f"{counts[('supported', 'before', 'true')]} | "
        f"{counts[('supported', 'after', 'true')]} |",
        f"| Unsubstantiated: individual runs (of {10 * n}) that returned True | "
        f"{counts[('unsubstantiated', 'before_runs_true')]} | "
        f"{counts[('unsubstantiated', 'after_runs_true')]} |",
        f"| Supported: individual runs (of {10 * n}) that returned True | "
        f"{counts[('supported', 'before_runs_true')]} | "
        f"{counts[('supported', 'after_runs_true')]} |",
        "",
        "## Who withheld the verdict (after)",
        "",
        "Runs where the outcome was not True, split by whether the model itself declined "
        "or a code check withheld the model's True or False.",
        "",
        "| Group | Model declined | Code withheld | Direction check withdrew "
        "| No usable quotation |",
        "| --- | ---: | ---: | ---: | ---: |",
        *withheld_rows(after),
        "",
        "## All cases",
        "",
        "S = supported (expected True), U = unsubstantiated (expected Insufficient), "
        "X = two extra cases reported outside the 20.",
        "",
        "| Case | Problem | Claim | Expected | Before | After | Change | Decisive evidence "
        "or failure (after) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
        *rows,
        "",
    ]
    (HERE / "results.md").write_text("\n".join(lines))
    print("\n".join(lines[:22]))


if __name__ == "__main__":
    main(*sys.argv[1:3])
