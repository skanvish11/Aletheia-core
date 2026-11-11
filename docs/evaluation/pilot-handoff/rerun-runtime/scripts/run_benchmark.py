"""Bounded, resumable evaluation. Offline dataset validation is the default."""

import argparse
import asyncio
import fcntl
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from evaluate_research import run as run_case

from aletheia.benchmark import benchmark_row, code_hash, load_benchmark, report
from aletheia.config import ConfigurationError, ProviderSettings
from aletheia.evaluation import dataset_hash, write_json

ROOT = Path(__file__).resolve().parents[1]


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def public_settings(settings):
    return settings.model_dump(exclude={"nebius_api_key", "tavily_api_key"})


def selected_cases(args):
    cases = load_benchmark(args.cases)
    chosen = [c for c in cases if c.split == args.split and (not args.pilot or c.pilot)]
    if args.limit is not None:
        chosen = chosen[: args.limit]
    if not chosen:
        raise ValueError("No selected cases")
    if (
        args.split == "reserved"
        and args.live
        and (not args.release_reserved or any(c.status == "proposed" for c in chosen))
    ):
        raise ValueError("Reserved evaluation requires reviewed labels and --release-reserved")
    return chosen


def recover_row(case, directory):
    """Never restart an attempted case, even if the process died before artifact capture."""
    artifact_path = directory / f"{case.id}.json"
    if artifact_path.exists():
        return benchmark_row(case, load_json(artifact_path))
    return benchmark_row(case, {"runner_error": "interrupted_before_artifact_capture"})


async def execute(args, cases, settings, *, executor=run_case):
    output = args.output
    expected = {
        "schema_version": "1.0",
        "dataset_sha256": dataset_hash(cases),
        "code_sha256": code_hash(ROOT),
        "config": public_settings(settings),
        "case_ids": [c.id for c in cases],
        "concurrency": args.concurrency,
        "pilot": args.pilot,
    }
    if args.resume:
        manifest = load_json(output / "manifest.json")
        if any(manifest.get(k) != value for k, value in expected.items()):
            raise ValueError("Resume dataset, implementation, selection, or configuration changed")
    else:
        output.mkdir(parents=True, exist_ok=False)
        manifest = {
            **expected,
            "started_at": datetime.now(UTC).isoformat(),
            "live": True,
            "human_acceptance_complete": False,
            "cost": "unknown",
            "attempt_policy": "one attempt per case; never silently rerun",
        }
        write_json(output / "manifest.json", manifest)
        write_json(output / "cases.json", [c.model_dump() for c in cases])
    # OS lock releases automatically after a crash; a second runner cannot start paid work.
    with (output / "run.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        rows = {}
        for case in cases:
            if (output / (case.id + ".started.json")).exists():
                rows[case.id] = recover_row(case, output / case.id)
        manifest["stopped_early"] = None

        def checkpoint():
            ordered = [rows[c.id] for c in cases if c.id in rows]
            write_json(output / "scores.json", ordered)
            write_json(output / "summary.json", report(ordered, len(cases)))
            manifest.update(
                recorded=len(ordered),
                not_run=len(cases) - len(ordered),
                updated_at=datetime.now(UTC).isoformat(),
            )
            write_json(output / "manifest.json", manifest)

        checkpoint()
        stop = asyncio.Event()

        async def one(case):
            write_json(
                output / (case.id + ".started.json"),
                {"id": case.id, "started_at": datetime.now(UTC).isoformat()},
            )
            child_args = SimpleNamespace(
                dotenv=None, model=None, output=output / case.id, refresh_first=False
            )
            try:
                await executor(child_args, [case], settings=settings)
                rows[case.id] = recover_row(case, child_args.output)
                child_manifest = child_args.output / "manifest.json"
                if child_manifest.exists() and load_json(child_manifest).get("stopped_early"):
                    stop.set()
                    manifest["stopped_early"] = "child_runner_or_configuration_failure"
            except asyncio.CancelledError:
                rows[case.id] = recover_row(case, child_args.output)
                raise
            except Exception:
                rows[case.id] = recover_row(case, child_args.output)
                stop.set()
                manifest["stopped_early"] = "runner_error"
            finally:
                checkpoint()

        pending = [c for c in cases if c.id not in rows]
        try:
            # Each cohort finishes before scheduling another. Each case owns a separate
            # backend/database/provider counter; concurrency cannot corrupt attribution.
            for offset in range(0, len(pending), args.concurrency):
                async with asyncio.TaskGroup() as group:
                    for case in pending[offset : offset + args.concurrency]:
                        group.create_task(one(case))
                if stop.is_set():
                    break
        except asyncio.CancelledError:
            manifest["stopped_early"] = "cancelled"
            raise
        finally:
            checkpoint()
        return len(rows) == len(cases) and not manifest["stopped_early"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--split", choices=["development", "reserved"], default="development")
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--concurrency", type=int, choices=range(1, 5), default=1)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--release-reserved", action="store_true")
    parser.add_argument("--dotenv", type=Path)
    parser.add_argument("--model")
    parser.add_argument("--thinking", choices=["default", "enabled", "disabled"], default="default")
    args = parser.parse_args(argv)
    try:
        if args.limit is not None and not 1 <= args.limit <= 1500:
            raise ValueError("Limit must be 1..1500")
        cases = selected_cases(args)
        if len(cases) > 1500:
            raise ValueError("At most 1500 cases per run")
        if args.pilot and len(cases) != 30:
            raise ValueError("A pilot must contain exactly the 30 designated cases")
        if not args.live:
            print(
                json.dumps(
                    {
                        "live": False,
                        "valid_selected_cases": len(cases),
                        "dataset_sha256": dataset_hash(cases),
                        "label_statuses": sorted({c.status for c in cases}),
                    }
                )
            )
            return 0
        if args.output is None:
            raise ValueError("Live evaluation requires an output directory")
        settings = ProviderSettings.from_environment(dotenv_path=args.dotenv)
        overrides = {"nebius_thinking": args.thinking}
        if args.model:
            overrides["nebius_model"] = args.model
        settings = ProviderSettings.model_validate({**settings.model_dump(), **overrides})
        if not settings.nebius_api_key or not settings.tavily_api_key or not settings.nebius_model:
            raise ConfigurationError(
                "Provider configuration is incomplete; configure both keys and model."
            )
        settings.validate_model_controls()
        return 0 if asyncio.run(execute(args, cases, settings)) else 1
    except ConfigurationError as exc:
        print(f"Benchmark stopped: {exc}")
        return 2
    except Exception:
        print(
            "Benchmark stopped: check dataset, output, resume configuration, and runner ownership."
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
