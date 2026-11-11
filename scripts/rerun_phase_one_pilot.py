"""Run the unchanged 30-case development pilot against the current backend once."""

import argparse
import asyncio
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Literal

from evaluate_research import run as run_case
from pydantic import ConfigDict

from aletheia.config import ProviderSettings
from aletheia.evaluation import EvaluationCase, dataset_hash, score, write_json

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "docs/evaluation/pilot-handoff"


class PilotCase(EvaluationCase):
    # Retain the legacy benchmark metadata, while using current request/label validation.
    model_config = ConfigDict(extra="allow", strict=True)
    split: Literal["development"]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_pilot():
    cases = [PilotCase.model_validate(c) for c in read_json(HANDOFF / "claims.json")]
    baseline = read_json(HANDOFF / "rerun/manifest.json")
    if len(cases) != 30 or [c.id for c in cases] != baseline["case_ids"]:
        raise ValueError("The pilot must retain the same ordered 30 cases.")
    if dataset_hash(cases) != baseline["dataset_sha256"]:
        raise ValueError("The pilot claims, labels or metadata changed.")
    return cases, baseline


def result_row(case, artifact):
    saved = artifact.get("investigation") or {}
    result = saved.get("result") or {}
    analysis = saved.get("claim_analysis") or {}
    unsupported = bool(saved.get("method_limitation"))
    factual_completed = saved.get("status") == "completed" and bool(result) and not unsupported
    usage = {"prompt_tokens": 0, "completion_tokens": 0}
    for event in artifact.get("events", []):
        if event.get("type") == "task_finished":
            for key in usage:
                number = event.get("payload", {}).get(key, "")
                if str(number).isdigit():
                    usage[key] += int(number)
    return {
        "id": case.id,
        "claim": case.claim,
        "status": saved.get("status", "runner_failed"),
        "stop_reason": saved.get("stop_reason"),
        "unsupported_method": unsupported,
        "factual_completed": factual_completed,
        "primary_type": analysis.get("primary_type"),
        "required_method": analysis.get("required_method"),
        "scope": analysis.get("scope"),
        "outcome": result.get("outcome"),
        "verdict": result.get("verdict"),
        "unable_to_decide_reason": result.get("unable_to_decide_reason"),
        "historical_label_match": score(case, artifact)["decision_label_match"],
        "expected": case.expected.verdict or case.expected.unable_to_decide_reason,
        "elapsed_seconds": artifact.get("elapsed_seconds"),
        "observed_usage": usage,
        "network_attempts": len(artifact.get("network_attempts", [])),
        "saved_checks": artifact.get("saved_checks", {}),
    }


def summary(rows, planned):
    from collections import Counter

    return {
        "planned": planned,
        "recorded": len(rows),
        "not_run": planned - len(rows),
        "execution_statuses": dict(Counter(r["status"] for r in rows)),
        "factual_completed": sum(r["factual_completed"] for r in rows),
        "unsupported_method": sum(r["unsupported_method"] for r in rows),
        "historical_label_matches": sum(r["historical_label_match"] for r in rows),
        "historical_label_denominator": planned,
        "observed_usage": {
            key: sum(r["observed_usage"][key] for r in rows)
            for key in ("prompt_tokens", "completion_tokens")
        },
        "network_attempts": sum(r["network_attempts"] for r in rows),
        "cost": "unknown; observed tokens are not a bill",
        "human_acceptance_complete": False,
        "note": "Historical labels remain AI proposals. Unsupported responses are separate from "
        "factual completion. Mixed-task historical agreement is not phase-one accuracy.",
    }


async def execute(output, cases, baseline, settings, *, executor=run_case):
    output.mkdir(parents=True, exist_ok=False)
    revision = await asyncio.to_thread(
        subprocess.check_output, ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    )
    dirty = await asyncio.to_thread(
        subprocess.check_output, ["git", "status", "--porcelain"], cwd=ROOT, text=True
    )
    manifest = {
        "revision": revision.strip(),
        "working_tree_dirty": bool(dirty.strip()),
        "dataset_sha256": dataset_hash(cases),
        "case_ids": [c.id for c in cases],
        "config": settings.model_dump(exclude={"nebius_api_key", "tavily_api_key"}),
        "concurrency": baseline["concurrency"],
        "live": True,
        "started_at": datetime.now(UTC).isoformat(),
        "stopped_early": None,
        "attempt_policy": "One fresh investigation per case; no automatic case reruns.",
    }
    write_json(output / "cases.json", [c.model_dump() for c in cases])
    rows = {}

    def checkpoint():
        ordered = [rows[c.id] for c in cases if c.id in rows]
        write_json(output / "scores.json", ordered)
        write_json(output / "summary.json", summary(ordered, len(cases)))
        write_json(output / "manifest.json", manifest)

    async def one(case):
        child = output / case.id
        write_json(output / (case.id + ".started.json"), {"id": case.id})
        try:
            await executor(
                SimpleNamespace(dotenv=None, model=None, output=child, refresh_first=False),
                [case],
                settings=settings,
            )
            artifact = read_json(child / (case.id + ".json"))
            child_manifest = read_json(child / "manifest.json")
            rows[case.id] = result_row(case, artifact)
            if child_manifest.get("stopped_early"):
                manifest["stopped_early"] = "child_runner_or_configuration_failure"
            rows[case.id]["restart_checks"] = child_manifest.get("restart_checks", [])
            rows[case.id]["restart_zero_provider_calls"] = child_manifest.get(
                "restart_zero_provider_calls"
            )
        except Exception:
            rows[case.id] = result_row(case, {})
            manifest["stopped_early"] = "runner_error"
        finally:
            checkpoint()

    checkpoint()
    try:
        for offset in range(0, len(cases), baseline["concurrency"]):
            async with asyncio.TaskGroup() as group:
                for case in cases[offset : offset + baseline["concurrency"]]:
                    group.create_task(one(case))
            if manifest["stopped_early"]:
                break
    except asyncio.CancelledError:
        manifest["stopped_early"] = "cancelled"
        raise
    finally:
        manifest["finished_at"] = datetime.now(UTC).isoformat()
        checkpoint()
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--dotenv", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    cases, baseline = load_pilot()
    if not args.live:
        print(
            json.dumps({"cases": len(cases), "dataset_sha256": dataset_hash(cases), "live": False})
        )
        return
    if args.output is None:
        parser.error("A fresh --output directory is required.")
    # Runtime loading only; credential values are never inspected, printed or persisted.
    loaded = ProviderSettings.from_environment(dotenv_path=args.dotenv)
    settings = ProviderSettings.model_validate({**loaded.model_dump(), **baseline["config"]})
    if not settings.nebius_api_key or not settings.tavily_api_key:
        raise SystemExit("Provider credentials are incomplete; no live run started.")
    settings.validate_model_controls()
    manifest = asyncio.run(execute(args.output, cases, baseline, settings))
    if manifest["stopped_early"]:
        raise SystemExit("Pilot stopped early; inspect the saved sanitized manifest.")


if __name__ == "__main__":
    main()
