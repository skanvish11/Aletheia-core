"""Capture real API responses (investigation, evidence, events) from the backend with
synthetic providers, for the web client's rendering regression test.

Usage, from the repository root with the backend environment active:
    python web/scripts/capture_backend_fixtures.py . web/src/fixtures/backend
No keys and no network: Settings is built directly, so .env is never loaded.
"""

import asyncio
import json
import sys
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

repo, out = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(repo / "tests"))

from httpx import ASGITransport, AsyncClient  # noqa: E402
from research_fixtures import Providers, terminal  # noqa: E402

from aletheia.api import create_app  # noqa: E402
from aletheia.budgets import RunBudget  # noqa: E402
from aletheia.config import Settings  # noqa: E402


class FinalDeadlineBudget(RunBudget):
    """Same as the backend test: the deadline passes while the explanation is finalized."""

    def reserve(self, provider, operation, units):
        if self.finalizing and self.used["model"] == 4:
            self.deadline = self.started - 1
        super().reserve(provider, operation, units)


CLAIM = "The Archive opened in 2000."

SCENARIOS = {
    "true": ({}, {}),
    "almost": (
        {"relation": "contradicts", "almost": True, "text": "The Archive opened in 2001."},
        {},
    ),
    "false": ({"relation": "contradicts", "independent": True}, {}),
    "conflicting": ({"relation": "mixed", "source_count": 2, "independent": True}, {}),
    "insufficient": ({"empty": True}, {}),
    "finalization-timeout": ({}, {"budget_factory": FinalDeadlineBudget}),
}


@asynccontextmanager
async def running(db, providers, **options):
    settings = Settings(database_path=db, research_enabled=True)
    app = create_app(settings, provider_factory=providers.factory, **options)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        yield client


async def capture(name, provider_options, app_options, tmp):
    db = Path(tmp) / f"{name}.sqlite3"
    async with running(db, Providers(**provider_options), **app_options) as client:
        created = await client.post("/investigations", json={"claim": CLAIM})
        run_id = created.json()["id"]
        investigation = await terminal(client, run_id)
        evidence = (await client.get(f"/investigations/{run_id}/evidence")).json()
        stream = (await client.get(f"/investigations/{run_id}/events")).text
    prefix = "data: "
    events = [
        json.loads(line[len(prefix) :]) for line in stream.splitlines() if line.startswith(prefix)
    ]
    result = investigation["result"] or {}
    print(
        f"{name:22} status={investigation['status']:9} stop={investigation['stop_reason']}"
        f" outcome={result.get('outcome')} verdict={result.get('verdict')}"
        f" reason={result.get('unable_to_decide_reason')}"
        f" explanation={len(result.get('explanation', []))}"
        f" events={len(events)}"
    )
    recording = {"investigation": investigation, "evidence": evidence, "events": events}
    (out / f"{name}.json").write_text(json.dumps(recording, indent=2) + "\n", encoding="utf-8")


async def main():
    with tempfile.TemporaryDirectory() as tmp:
        for name, (provider_options, app_options) in SCENARIOS.items():
            await capture(name, provider_options, app_options, tmp)


out.mkdir(parents=True, exist_ok=True)
asyncio.run(main())
