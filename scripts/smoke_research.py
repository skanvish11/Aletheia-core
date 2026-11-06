"""Explicitly authorized live one-claim smoke check; never invoked by default tests/CI."""

import argparse
import asyncio
import json
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from aletheia.api import create_app
from aletheia.config import ConfigurationError, ProviderSettings, Settings
from aletheia.providers.errors import ProviderError
from aletheia.providers.nebius import NebiusProvider
from aletheia.providers.tavily import TavilyProvider


async def run(args):
    settings = ProviderSettings.from_environment(dotenv_path=args.dotenv)

    @asynccontextmanager
    async def providers():
        async with NebiusProvider(settings) as model, TavilyProvider(settings) as search:
            yield model, search, settings.nebius_model

    with tempfile.TemporaryDirectory(prefix="aletheia-live-research-") as directory:
        app = create_app(
            Settings(database_path=Path(directory) / "smoke.sqlite3", research_enabled=True),
            provider_factory=providers,
        )
        async with (
            app.router.lifespan_context(app),
            AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
        ):
            response = await client.post("/investigations", json={"claim": args.claim})
            response.raise_for_status()
            location = response.json()["links"]["self"]
            async with asyncio.timeout(260):
                while True:
                    saved = (await client.get(location)).json()
                    if saved["status"] not in {"queued", "running"}:
                        break
                    await asyncio.sleep(0.25)
            evidence = (await client.get(location + "/evidence")).json()
            duplicate = (await client.post("/investigations", json={"claim": args.claim})).json()
            if duplicate != saved:
                raise RuntimeError("Saved reuse changed the investigation.")
            # Only sanitized public artifacts; never raw HTTP bodies, prompts or settings.
            report = {
                "live": True,
                "investigation": saved,
                "evidence": evidence,
                "citation_review": "pending_human_review",
                "saved_reuse_identical": True,
            }
            args.output.write_text(json.dumps(report, indent=2) + "\n")
            print(
                json.dumps(
                    {
                        "status": saved["status"],
                        "verdict": (saved["result"] or {}).get("verdict"),
                        "citation_review": "pending_human_review",
                    }
                )
            )
            return saved["status"] == "completed"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true", help="Explicitly authorize bounded paid provider calls"
    )
    parser.add_argument("--claim", required=True)
    parser.add_argument("--dotenv", type=Path, help="Explicit runtime-only settings file")
    parser.add_argument(
        "--output", type=Path, required=True, help="Public research report; review before sharing"
    )
    args = parser.parse_args()
    if not args.live:
        parser.error("No provider calls made. Pass --live only after authorizing live research.")
    try:
        complete = asyncio.run(run(args))
    except (ConfigurationError, ProviderError, TimeoutError, OSError, RuntimeError):
        raise SystemExit("Live research check failed; no private diagnostics printed.") from None
    raise SystemExit(0 if complete else 1)


if __name__ == "__main__":
    main()
