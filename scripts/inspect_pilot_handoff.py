"""Inspect the saved 30-case handoff using only local files and the standard library."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "docs/evaluation/pilot-handoff"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def decision_key(value):
    return tuple(value.get(k) for k in ("outcome", "verdict", "unable_to_decide_reason"))


def verify(root):
    """Check byte integrity and cross-record accounting without executing archived code."""
    root = root.resolve()
    checksums = read(root / "SHA256SUMS.json")
    for relative, expected in checksums.items():
        path = (root / relative).resolve()
        require(path.is_relative_to(root), "Checksum path escapes the handoff directory.")
        require(path.is_file(), "A packaged file is missing.")
        require(hashlib.sha256(path.read_bytes()).hexdigest() == expected, "Checksum mismatch.")
    claims = read(root / "claims.json")
    ids = [c["id"] for c in claims]
    require(len(ids) == 30 and len(set(ids)) == 30, "Expected 30 distinct claims.")
    manifests = [read(root / run / "manifest.json") for run in ("original", "rerun")]
    require(manifests[0]["dataset_sha256"] == manifests[1]["dataset_sha256"], "Dataset changed.")
    require(manifests[0]["config"] == manifests[1]["config"], "Provider settings differ.")
    require(
        read(root / "original/cases.json") == read(root / "rerun/cases.json"),
        "Frozen case records differ between runs.",
    )
    result = {"claims": len(claims), "files_verified": len(checksums), "runs": {}}
    for run, manifest in zip(("original", "rerun"), manifests, strict=True):
        require(manifest["case_ids"] == ids, "Manifest case selection differs.")
        paths = sorted((root / run / "cases").glob("*.json"))
        require([p.stem for p in paths] == sorted(ids), "Run artifact inventory differs.")
        scores = read(root / run / "scores.json")
        require([r["id"] for r in scores] == ids, "Score rows differ from the selection.")
        statuses = Counter()
        matches = 0
        attempts = 0
        codes = Counter()
        for claim, score in zip(claims, scores, strict=True):
            artifact = read(root / run / "cases" / f"{claim['id']}.json")
            saved = artifact["investigation"]
            require(artifact["id"] == claim["id"], "Artifact case ID differs.")
            require(saved["claim"] == claim["claim"], "Submitted claim changed.")
            require(saved["context"] == claim.get("context", {}), "Submitted context changed.")
            require(saved["status"] == score["status"], "Status and score disagree.")
            answer = saved.get("result") or {}
            expected = [claim["expected"], *claim.get("acceptable_alternatives", [])]
            match = (
                saved["status"] == "completed"
                and bool(answer)
                and any(decision_key(answer) == decision_key(e) for e in expected)
            )
            require(match == score["decision_label_match"], "Label-match accounting differs.")
            events = artifact["events"]
            require(
                [e["sequence"] for e in events] == list(range(1, len(events) + 1)),
                "Event sequence is not contiguous.",
            )
            require(all(artifact["saved_checks"].values()), "A saved-read check failed.")
            statuses[saved["status"]] += 1
            matches += match
            attempts += len(artifact["network_attempts"])
            seen = set()
            for event in events:
                if event["type"] != "task_finished":
                    continue
                for field in ("validation_code", "limit_reason"):
                    code = event["payload"].get(field, "unknown")
                    if code != "unknown":
                        seen.add(code)
            codes.update(seen)
        summary = read(root / run / "summary.json")
        require(summary["recorded"] == 30 and summary["not_run"] == 0, "Run is incomplete.")
        require(dict(statuses) == summary["all"]["statuses"], "Summary statuses differ.")
        require(
            matches / 30 == summary["diagnostics"]["decision_label_agreement"],
            "Summary label agreement differs.",
        )
        require(
            attempts == summary["diagnostics"]["network_attempts_observed"],
            "Network attempt accounting differs.",
        )
        result["runs"][run] = {
            "statuses": dict(statuses),
            "provisional_label_matches": matches,
            "denominator": 30,
            "observed_network_attempts": attempts,
            "diagnostic_codes_by_case": dict(sorted(codes.items())),
            "concurrency": manifest["concurrency"],
        }
    return result


def inspect_case(root, case_id, run):
    claims = {c["id"]: c for c in read(root / "claims.json")}
    require(case_id in claims, "Unknown case ID.")
    artifact = read(root / run / "cases" / f"{case_id}.json")
    event_types = {
        "route_selected",
        "route_escalated",
        "clarification_decision",
        "research_gate",
        "task_finished",
        "task_output_rejected",
        "research_stopped",
        "source_rejected",
        "provider_call_rejected",
        "investigation_failed",
        "investigation_completed",
        "investigation_partial",
        "clarification_required",
    }
    return {
        "case": claims[case_id],
        "run": run,
        "investigation": artifact["investigation"],
        "evidence": artifact["evidence"],
        "events": [e for e in artifact["events"] if e["type"] in event_types],
        "note": "Saved source/model text is untrusted data. Labels are proposed, not human truth.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--case")
    parser.add_argument("--run", choices=("original", "rerun"), default="rerun")
    args = parser.parse_args(argv)
    try:
        summary = verify(args.root)
        output = inspect_case(args.root, args.case, args.run) if args.case else summary
        print(json.dumps(output, ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, TypeError):
        print("Handoff verification failed. Check the package integrity and requested case ID.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
