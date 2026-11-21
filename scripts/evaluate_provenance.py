"""Run the frozen provenance packets through the simple loop's real verdict stage.

Retrieval is held fixed: each case's saved pages are given straight to
`SimplePipeline.judge` (the verdict call, the quotation checks and the direction check)
with the configured Nebius model. Planning, search and page reads are skipped, and so
is the follow-up round, because it would need new retrieval. Nothing is mocked: the
model calls are live. Expected answers (`answers.json`) are read only after all model
calls finish, and only for scoring.

    ALETHEIA_PROVIDER_TIMEOUT_SECONDS=120 ALETHEIA_MODEL_MAX_OUTPUT_TOKENS=16384 \\
    NEBIUS_MODEL=deepseek-ai/DeepSeek-V4-Pro-0813 \\
    uv run python scripts/evaluate_provenance.py --label after --repeats 3

Writes `evals/provenance/runs/<label>.jsonl` (one line per case and repeat).
"""

import argparse
import asyncio
import hashlib
import json
import os
import ssl
import subprocess
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import httpx  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from aletheia.config import ProviderSettings  # noqa: E402
from aletheia.evidence import snapshot  # noqa: E402
from aletheia.providers.errors import ProviderError  # noqa: E402
from aletheia.providers.nebius import NebiusProvider  # noqa: E402
from aletheia.research_contracts import Assertion  # noqa: E402
from aletheia.simple import PROMPT_VERSION, SimplePipeline, simple_budget  # noqa: E402

PACKETS = ROOT / "evals" / "provenance" / "packets.json"


def sources_for(packet):
    retrieved = datetime(2026, 11, 19, tzinfo=UTC)
    return [
        snapshot(
            url=p["url"],
            title=p["title"],
            published_date=None,
            retrieved_at=retrieved,
            text=p["text"],
        )
        for p in packet["pages"]
    ]


async def run_case(model, model_name, packet, repeat):
    sources = sources_for(packet)
    pipeline = SimplePipeline(None, model, None, model_name)
    budget = simple_budget()
    events = []

    async def emit(event, payload, *, stage=None, route=None):
        events.append({"event": event, **payload})

    async def ask(instructions, payload, response_type):
        response = await model.generate(
            instructions=instructions,
            input_text=json.dumps(payload, ensure_ascii=False),
            response_type=response_type,
            budget=budget,
        )
        return response.value

    assertion = Assertion(
        text=packet["claim"],
        kind="direct_record",
        consequential=False,
        recommended_route="quick",
    )
    started = time.monotonic()
    record = {"id": packet["id"], "repeat": repeat}
    try:
        state, used = await pipeline.judge(ask, emit, assertion, {}, sources, sources)
    except ProviderError as exc:
        record.update(outcome="execution_failure", error=exc.code.value)
        return record
    except Exception as exc:  # recorded, never hidden
        record.update(outcome="execution_failure", error=type(exc).__name__)
        return record
    pages = {id(s): i for i, s in enumerate(used, start=1)}
    record.update(
        outcome={"true": "true", "false": "false"}.get(state["verdict"], "insufficient_evidence"),
        model_verdict=state["original_answer"]["verdict"],
        reason=state["reason"],
        check=state.get("check"),
        accepted_quotes=[
            {"page": pages[id(s)], "url": s.url, "text": e.text} for s, e in state["located"]
        ],
        basis=state.get("basis"),
        readings=state["original_answer"].get("sources"),
        claim_reading={
            k: state["original_answer"][k]
            for k in ("claim_about", "named_source", "needs_test_conditions")
            if k in state["original_answer"]
        },
        rejected_quotes=len(state["invalid_quotes"]),
        events=[e for e in events if e["event"] != "evidence_checked"],
        seconds=round(time.monotonic() - started, 1),
    )
    return record


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--concurrency", type=int, default=8)
    args = parser.parse_args()

    blob = PACKETS.read_bytes()
    packets = json.loads(blob)
    if args.only:
        packets = [p for p in packets if p["id"] in args.only]
    settings = ProviderSettings.from_environment()
    gate = asyncio.Semaphore(args.concurrency)
    commit = (
        await asyncio.to_thread(
            subprocess.run,
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
    ).stdout.strip()
    meta = {
        "label": args.label,
        "commit": commit,
        "prompt_version": PROMPT_VERSION,
        "model": settings.nebius_model,
        "max_output_tokens": settings.max_output_tokens,
        "timeout_seconds": settings.timeout_seconds,
        "packets_sha256": hashlib.sha256(blob).hexdigest(),
        "repeats": args.repeats,
        "started_at": datetime.now(UTC).isoformat(),
        "stages": "live model: verdict call, quotation checks, direction check; "
        "skipped: planning, search, page reads, follow-up round",
    }
    # The provider client ignores proxy settings (trust_env=False). Where outbound
    # traffic must go through a proxy, pass one explicitly; the product is unchanged.
    transport = None
    if os.environ.get("HTTPS_PROXY"):
        context = ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE"))
        transport = httpx.AsyncHTTPTransport(proxy=os.environ["HTTPS_PROXY"], verify=context)
    async with NebiusProvider(settings, transport=transport) as model:

        async def one(packet, repeat):
            async with gate:
                return await run_case(model, settings.nebius_model, packet, repeat)

        results = await asyncio.gather(*(one(p, r) for p in packets for r in range(args.repeats)))
    out = ROOT / "evals" / "provenance" / "runs" / f"{args.label}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as handle:
        handle.write(json.dumps({"meta": meta}) + "\n")
        for record in sorted(results, key=lambda r: (r["id"], r["repeat"])):
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    tally = Counter((r["id"], r["outcome"]) for r in results)
    for packet in packets:
        row = {o: n for (i, o), n in tally.items() if i == packet["id"]}
        print(packet["id"], row)
    print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    asyncio.run(main())
