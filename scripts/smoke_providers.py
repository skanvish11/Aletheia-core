"""Opt-in provider checks. Prints safe measurements, never keys or response bodies."""

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from aletheia.config import ConfigurationError
from aletheia.providers.common import CallBudget, ProviderError
from aletheia.providers.nebius import NebiusProvider
from aletheia.providers.settings import ProviderSettings
from aletheia.providers.tavily import TavilyProvider


class ShortReply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    year: int


class LongReply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: Annotated[list[ShortReply], Field(min_length=12, max_length=12)]


async def measure(settings: ProviderSettings, *, samples: int, deadline_seconds: float) -> dict:
    # At most one retry across the model samples, one across search, one across extraction.
    budget = CallBudget(2 * samples + 1, 2, 2, time.monotonic() + deadline_seconds)
    report = {
        "checked_at": datetime.now(UTC).isoformat(),
        "model": settings.nebius_model,
        "response_format": settings.nebius_response_format,
        "samples_per_model_task": samples,
        "deadline_seconds": deadline_seconds,
        "checks": [],
        "limitations": [
            "Small integration sample; not a latency SLA or research-quality evaluation.",
            "Live failures are not deliberately induced; retry timing is tested offline.",
            "Usage is reported when supplied; failed requests may still incur provider charges.",
        ],
    }
    try:
        async with NebiusProvider(settings) as model:
            for sample in range(samples):
                for label, response_type, text in (
                    ("short", ShortReply, "Return label alpha and year 2023."),
                    (
                        "long",
                        LongReply,
                        "Return 12 items with labels item-1 through item-12, each with year 2023.",
                    ),
                ):
                    started = time.monotonic()
                    try:
                        result = await model.generate(
                            instructions="Copy the requested synthetic records exactly.",
                            input_text=text,
                            response_type=response_type,
                            budget=budget,
                        )
                        correct = (
                            result.value.label == "alpha" and result.value.year == 2023
                            if label == "short"
                            else all(
                                item.label == f"item-{i}" and item.year == 2023
                                for i, item in enumerate(result.value.items, 1)
                            )
                        )
                        report["checks"].append(
                            {
                                "check": "nebius_" + label,
                                "sample": sample + 1,
                                "passed": correct,
                                "elapsed_seconds": time.monotonic() - started,
                                "usage": result.usage.model_dump() if result.usage else None,
                            }
                        )
                    except ProviderError as exc:
                        report["checks"].append(
                            {
                                "check": "nebius_" + label,
                                "sample": sample + 1,
                                "passed": False,
                                "error": exc.code.value,
                                "elapsed_seconds": time.monotonic() - started,
                            }
                        )
                        # Do not spend further requests after a failed model check.
                        raise
    except ProviderError as exc:
        if not report["checks"]:
            report["checks"].append(
                {"check": "nebius_setup", "passed": False, "error": exc.code.value}
            )

    try:
        async with TavilyProvider(settings) as web:
            started = time.monotonic()
            search = await web.search(
                "site:python.org Python programming language", budget=budget, max_results=2
            )
            report["checks"].append(
                {
                    "check": "tavily_search",
                    "passed": bool(search.results),
                    "result_count": len(search.results),
                    "elapsed_seconds": time.monotonic() - started,
                    "usage": search.usage.model_dump() if search.usage else None,
                }
            )
            if search.results:
                started = time.monotonic()
                extracted = await web.extract([search.results[0].url], budget=budget)
                report["checks"].append(
                    {
                        "check": "tavily_extract",
                        "passed": extracted.pages[0].error is None,
                        "characters": len(extracted.pages[0].content or ""),
                        "error": extracted.pages[0].error,
                        "elapsed_seconds": time.monotonic() - started,
                        "usage": extracted.usage.model_dump() if extracted.usage else None,
                    }
                )
    except ProviderError as exc:
        report["checks"].append({"check": "tavily", "passed": False, "error": exc.code.value})

    report["attempts"] = [asdict(attempt) for attempt in budget.attempts]
    report["attempt_units"] = dict(budget.used)
    report["passed"] = len(report["checks"]) == 2 * samples + 2 and all(
        c["passed"] for c in report["checks"]
    )
    report["latency_seconds"] = {}
    for label in ("nebius_short", "nebius_long", "tavily_search", "tavily_extract"):
        times = [
            c["elapsed_seconds"] for c in report["checks"] if c["check"] == label and c["passed"]
        ]
        if times:
            report["latency_seconds"][label] = {
                "count": len(times),
                "median": statistics.median(times),
                "max": max(times),
            }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true", help="Enable bounded billable provider calls."
    )
    parser.add_argument(
        "--dotenv", type=Path, help="Exact runtime settings file; never printed or copied."
    )
    parser.add_argument(
        "--model", help="Explicit Nebius model; overrides NEBIUS_MODEL for this run."
    )
    parser.add_argument("--samples", type=int, choices=range(1, 4), default=1)
    parser.add_argument("--deadline-seconds", type=int, choices=range(30, 301), default=180)
    parser.add_argument("--output", type=Path, help="Write a new safe JSON measurement report.")
    args = parser.parse_args(argv)
    if not args.live:
        print("No calls made. Use --live to enable the provider checks.")
        return 2
    if args.dotenv is not None and not args.dotenv.is_file():
        print("The explicit runtime settings file does not exist; no calls made.")
        return 2
    try:
        settings = ProviderSettings.from_environment(dotenv_path=args.dotenv)
        values = settings.model_dump()
        if args.model:
            values["nebius_model"] = args.model
        # Keep the explicit live workflow small even if the application's settings are larger.
        values["max_retries"] = min(settings.max_retries, 1)
        values["max_output_tokens"] = min(settings.max_output_tokens, 2048)
        settings = ProviderSettings(**values)
    except (ConfigurationError, ValidationError):
        print("Provider configuration is invalid; values hidden.")
        return 2
    missing = [
        name
        for name, value in (
            ("NEBIUS_API_KEY", settings.nebius_api_key),
            ("TAVILY_API_KEY", settings.tavily_api_key),
            ("NEBIUS_MODEL (or --model)", settings.nebius_model),
        )
        if value is None
    ]
    if missing:
        print("No calls made. Missing settings: " + ", ".join(missing))
        return 2
    # Reserve a new report path before spending credits; never overwrite a file.
    try:
        output = args.output.open("x") if args.output else None
    except OSError:
        print("Cannot create report file; no calls made.")
        return 2
    try:
        report = asyncio.run(
            measure(settings, samples=args.samples, deadline_seconds=args.deadline_seconds)
        )
        serialized = json.dumps(report, indent=2)
        print(serialized)
        if output:
            output.write(serialized + "\n")
        return 0 if report["passed"] else 1
    finally:
        if output:
            output.close()


if __name__ == "__main__":
    raise SystemExit(main())
