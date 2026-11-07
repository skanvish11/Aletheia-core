"""Bounded live evaluation with public artifacts; offline validation is the default."""

import argparse
import asyncio
import json
import subprocess
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import httpx
from pydantic import ValidationError

from aletheia.api import create_app
from aletheia.config import ConfigurationError, ProviderSettings, Settings
from aletheia.evaluation import capture, dataset_hash, load_cases, score, summarize, write_json
from aletheia.providers.errors import ProviderError
from aletheia.providers.nebius import NebiusProvider
from aletheia.providers.tavily import TavilyProvider


class MeteredTransport(httpx.AsyncBaseTransport):
    """Count actual network attempts without retaining headers, URLs, or bodies."""

    def __init__(self, provider, attempts):
        self.provider = provider
        self.attempts = attempts
        self.inner = httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request):
        record = {"provider": self.provider, "status_code": None}
        self.attempts.append(record)
        started = time.monotonic()
        try:
            response = await self.inner.handle_async_request(request)
            record["status_code"] = response.status_code
            return response
        finally:
            record["headers_elapsed_seconds"] = round(time.monotonic() - started, 3)

    async def aclose(self):
        await self.inner.aclose()


class DiagnosticModel(NebiusProvider):
    """Keep safe budget outcomes even when no final result can be saved."""

    def __init__(self, settings, *, attempts, budgets):
        super().__init__(settings, transport=MeteredTransport("nebius", attempts))
        self.budgets = budgets

    async def generate(self, **kwargs):
        budget = kwargs["budget"]
        if not any(existing is budget for existing in self.budgets):
            self.budgets.append(budget)
        return await super().generate(**kwargs)


async def run(args, cases):
    settings = ProviderSettings.from_environment(dotenv_path=args.dotenv)
    if args.model:
        settings = ProviderSettings.model_validate(
            {**settings.model_dump(), "nebius_model": args.model}
        )
    if not settings.nebius_api_key or not settings.tavily_api_key or not settings.nebius_model:
        raise ConfigurationError("Provider configuration is incomplete")
    settings.validate_model_controls()
    # A fresh directory means no overwrite and no silent reuse of earlier evaluations.
    args.output.mkdir(parents=True, exist_ok=False)
    attempts = []
    budgets = []

    @asynccontextmanager
    async def providers():
        async with (
            DiagnosticModel(settings, attempts=attempts, budgets=budgets) as model,
            TavilyProvider(settings, transport=MeteredTransport("tavily", attempts)) as search,
        ):
            yield model, search, settings.nebius_model

    revision_result = await asyncio.to_thread(
        subprocess.run, ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    )
    revision = revision_result.stdout.strip()
    dirty = bool(
        (
            await asyncio.to_thread(
                subprocess.run,
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=True,
            )
        ).stdout
    )
    manifest = {
        "started_at": datetime.now(UTC).isoformat(),
        "revision": revision,
        "working_tree_dirty": dirty,
        "dataset_sha256": dataset_hash(cases),
        "model": settings.nebius_model,
        "response_format": settings.nebius_response_format,
        "nebius_thinking": settings.nebius_thinking,
        "max_output_tokens": settings.max_output_tokens,
        "provider_timeout_seconds": settings.timeout_seconds,
        "max_retries": settings.max_retries,
        "case_ids": [c.id for c in cases],
        "refresh_first": args.refresh_first,
        "cost": "unknown; no pricing estimate substituted for billed cost",
        "human_review": "pending",
        "live": True,
    }
    write_json(args.output / "manifest.json", manifest)
    rows, artifacts, restart_checks = [], [], []
    manifest["restart_zero_provider_calls"] = None
    try:
        write_json(args.output / "cases.json", [c.model_dump() for c in cases])
        database = args.output / "investigations.sqlite3"
        app = create_app(
            Settings(database_path=database, research_enabled=True), provider_factory=providers
        )
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client,
        ):
            for index, case in enumerate(cases):
                before = len(attempts)
                budget_start = len(budgets)
                try:
                    artifact = await capture(
                        client,
                        case,
                        call_count=lambda: len(attempts),
                        refresh=args.refresh_first and index == 0,
                    )
                except Exception:
                    # Retain attempted cases without exception text or provider bodies.
                    artifact = {"id": case.id, "live": True, "runner_error": "capture_failed"}
                artifact["network_attempts"] = attempts[before:]
                artifact["budget_attempts"] = [
                    [asdict(attempt) for attempt in budget.attempts]
                    for budget in budgets[budget_start:]
                ]
                artifacts.append(artifact)
                try:
                    row = score(case, artifact)
                except Exception:
                    artifact["runner_error"] = "scoring_failed"
                    row = score(case, {})
                rows.append(row)
                write_json(args.output / f"{case.id}.json", artifact)
                write_json(args.output / "scores.json", rows)
                write_json(args.output / "summary.json", summarize(rows, len(cases)))
                print(
                    json.dumps(
                        {
                            "id": case.id,
                            "status": rows[-1]["status"],
                            "network_attempts": len(attempts) - before,
                        }
                    ),
                    flush=True,
                )
                # Do not keep charging after an account/configuration failure or lost control.
                if artifact.get("runner_error") or any(
                    a["status_code"] in {400, 401, 402, 403, 404, 422, 432, 433}
                    for a in attempts[before:]
                ):
                    manifest["stopped_early"] = "runner_or_provider_configuration_failure"
                    break
        # Read-only restart verifies persistence, with no provider factory and no credentials.
        restart_before = len(attempts)
        reopened = create_app(Settings(database_path=database))
        async with (
            reopened.router.lifespan_context(reopened),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=reopened), base_url="http://test"
            ) as client,
        ):
            for artifact in artifacts:
                if saved := artifact.get("investigation"):
                    response = await client.get(saved["links"]["self"])
                    response.raise_for_status()
                    restart_checks.append(
                        {"id": artifact["id"], "unchanged": response.json() == saved}
                    )
        manifest["restart_zero_provider_calls"] = len(attempts) == restart_before
    except asyncio.CancelledError:
        manifest["stopped_early"] = "cancelled"
        raise
    except Exception:
        # Includes artifact I/O, scoring, application lifetime, and restart failures.
        # Stop further paid work; retain fixed codes without private exception text.
        manifest["stopped_early"] = "runner_error"
    finally:
        manifest.update(
            finished_at=datetime.now(UTC).isoformat(),
            network_attempts=len(attempts),
            restart_checks=restart_checks,
            recorded=len(rows),
            not_run=len(cases) - len(rows),
        )
        # Try each output independently: a failed case/score write must not prevent
        # final accounting. A persistently unwritable filesystem cannot be repaired here.
        for filename, value in (
            ("scores.json", rows),
            ("summary.json", summarize(rows, len(cases))),
            ("manifest.json", manifest),
        ):
            try:
                write_json(args.output / filename, value)
            except Exception:
                manifest["stopped_early"] = "artifact_write_failed"
                print("Evaluation artifact could not be saved; check output storage.", flush=True)
    return (
        "stopped_early" not in manifest
        and len(rows) == len(cases)
        and all(r["status"] == "completed" for r in rows)
        and all(check["unchanged"] for check in restart_checks)
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--dotenv", type=Path)
    parser.add_argument("--model")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--refresh-first", action="store_true")
    args = parser.parse_args(argv)
    try:
        cases = load_cases(args.cases)
        if not 1 <= args.limit <= 20:
            parser.error("--limit must be 1 to 20")
        cases = cases[: args.limit]
        if not args.live:
            print(
                json.dumps(
                    {
                        "valid_cases": len(cases),
                        "live": False,
                        "labels": sorted({c.status for c in cases}),
                    }
                )
            )
            return 0
        if args.output is None:
            parser.error("--live requires a new --output directory")
        return 0 if asyncio.run(run(args, cases)) else 1
    except ConfigurationError as exc:
        # ConfigurationError contains fixed guidance, never supplied values.
        print(f"Evaluation stopped: {exc}")
        return 2
    except (ValueError, ValidationError, ProviderError, OSError):
        print(
            "Evaluation stopped: check input paths, dataset, and runtime configuration. "
            "No private diagnostics printed."
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
