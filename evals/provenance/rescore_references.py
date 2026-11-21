"""Re-score recorded model answers under each trusted-reference rule, with no model calls.

The rule only changes code's decision over the model's answer, so the same answers can
be scored under every rule. Answers whose verdict the basis check withheld are decided
again; every other outcome stays as recorded. A verdict restored this way did not go
through the direction check, which runs only on a verdict that stands (in these runs the
direction check never withdrew a verdict the basis check had allowed).

    uv run python evals/provenance/rescore_references.py \\
        evals/provenance/runs/after.jsonl <trusted replay directory>
"""

import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from aletheia.evidence import snapshot  # noqa: E402
from aletheia.one_call import REFERENCE_MODES, Answer, basis_check, offer_pages  # noqa: E402
from aletheia.trusted_evaluation import (  # noqa: E402
    EVIDENCE,
    load_pages,
    ranked_pages,
    trusted_claims,
    trusted_rows,
)

HERE = Path(__file__).parent


def decide(answer_fields, valid, originals, urls, mode):
    answer = Answer.model_validate(answer_fields)
    if answer.verdict not in {"true", "false"} or not valid:
        return "cannot_settle"
    qualifies = basis_check(answer, valid, originals, urls, references=mode)["qualifies"]
    return answer.verdict if qualifies else "cannot_settle"


def frozen_cases(path):
    packets = {p["id"]: p for p in json.loads((HERE / "packets.json").read_text())}
    answers = {a["id"]: a for a in json.loads((HERE / "answers.json").read_text())}
    runs = [json.loads(line) for line in Path(path).read_text().splitlines()[1:]]
    now = datetime(2026, 11, 19, tzinfo=UTC)
    counts = Counter()
    for run in runs:
        packet, expected = packets[run["id"]], answers[run["id"]]
        sources = [
            snapshot(
                url=p["url"],
                title=p["title"],
                published_date=None,
                retrieved_at=now,
                text=p["text"],
            )
            for p in packet["pages"]
        ]
        used, _ = offer_pages(packet["claim"], sources, first=sources)
        withheld = any(e.get("reason") == "no_qualifying_basis" for e in run["events"])
        for mode in REFERENCE_MODES:
            outcome = run["outcome"]
            if withheld:
                fields = {
                    **run["claim_reading"],
                    "sources": run["readings"],
                    "original_record_not_supplied": "none",
                    "verdict": run["model_verdict"],
                    "quotes": [
                        {"page": q["page"], "text": q["text"]} for q in run["accepted_quotes"]
                    ],
                    "reason": "r",
                }
                verdict = decide(
                    fields,
                    run["accepted_quotes"],
                    [s.original_text for s in used],
                    [s.url for s in used],
                    mode,
                )
                outcome = {"cannot_settle": "insufficient_evidence"}.get(verdict, verdict)
            counts[(mode, expected["group"], outcome)] += 1
    return counts


def trusted(directory):
    """Each trusted claim's verdict under each rule, from a baseline_verdict.py run."""
    claims = {c.id: c.claim for c in trusted_claims()}
    verdicts = {}
    for path in sorted(Path(directory, "claims").glob("*.json")):
        artifact = json.loads(path.read_text())
        pages = load_pages(EVIDENCE, artifact["id"])
        ranked = ranked_pages(claims[artifact["id"]], pages)[:6]
        originals = [p["original_text"] for p in ranked]
        urls = [p["url"] for p in artifact["pages"]]
        for mode in REFERENCE_MODES:
            verdicts[(mode, artifact["id"])] = decide(
                artifact["original_answer"], artifact["quotes"], originals, urls, mode
            )
    return verdicts


def main(frozen_path, trusted_dir):
    counts = frozen_cases(frozen_path)
    print("Frozen cases (runs of 30 per group):")
    for mode in REFERENCE_MODES:
        print(
            f"  {mode:18} unsubstantiated True: {counts[(mode, 'unsubstantiated', 'true')]:2}"
            f"   supported True: {counts[(mode, 'supported', 'true')]:2}"
        )
    verdicts = trusted(trusted_dir)
    expected = {row["id"]: row["verdict"] for row in trusted_rows()}
    print("Trusted claims (of 77):")
    for mode in REFERENCE_MODES:
        right = answered = correct = 0
        for (m, cid), verdict in verdicts.items():
            if m != mode:
                continue
            label = expected[cid]
            correct += verdict == label
            if verdict in {"true", "false"}:
                answered += 1
                right += verdict == label
        print(
            f"  {mode:18} correct: {correct:2}   true/false given: {answered:2}   right: {right:2}"
        )


if __name__ == "__main__":
    main(*sys.argv[1:3])
