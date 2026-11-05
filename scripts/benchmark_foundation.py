"""Opt-in localhost benchmark using disposable synthetic data, never real dotenv files.

Example: uv run --locked python scripts/benchmark_foundation.py --output results.json
Compare sources with --variant baseline=/path/to/baseline/src --variant candidate=/path/to/src.
"""

import argparse
import asyncio
import hashlib
import json
import math
import os
import platform
import random
import socket
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import httpx

from aletheia.contracts import InvestigationRequest
from aletheia.storage import Storage

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ("saved_read", "saved_duplicate", "new", "concurrent_duplicate", "concurrent_new")
STAMP = "2026-01-01T00:00:00+00:00"


def fixture(index):
    return {
        "claim": f"Synthetic city {index} has population {100000 + index}.",
        "context": {"notes": "Benchmark fixture; no research performed."},
    }


def identity(index):
    return str(uuid5(NAMESPACE_URL, f"aletheia-benchmark/{index}"))


async def seed(path, size):
    await Storage(path).initialize()
    # Setup is excluded from timings. Terminal fixtures leave active-queue capacity free.
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA foreign_keys = ON")
        for index in range(size):
            payload = fixture(index)
            record_id = identity(index)
            db.execute(
                "INSERT INTO claim_requests VALUES (?, ?, ?, ?, ?)",
                (
                    record_id,
                    payload["claim"],
                    json.dumps(payload["context"]),
                    InvestigationRequest(**payload).request_key(),
                    STAMP,
                ),
            )
            db.execute(
                """INSERT INTO investigations
                (id, claim_request_id, version, status, created_at, finished_at, error_json)
                VALUES (?, ?, 1, 'failed', ?, ?, ?)""",
                (
                    record_id,
                    record_id,
                    STAMP,
                    STAMP,
                    json.dumps({"message": "Synthetic terminal fixture; no research performed."}),
                ),
            )
            db.executemany(
                "INSERT INTO events VALUES (?, ?, ?, ?, NULL, '{}')",
                [
                    (record_id, 1, STAMP, "investigation_queued"),
                    (record_id, 2, STAMP, "investigation_failed"),
                ],
            )


def source_digest(source):
    digest = hashlib.sha256()
    for file in sorted((source / "aletheia").glob("*.py")):
        digest.update(file.name.encode())
        digest.update(file.read_bytes())
    return digest.hexdigest()


@contextmanager
def server(directory, source):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    process = subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--serve",
            str(directory / "bench.db"),
            "--port",
            str(port),
            "--expected-source",
            source_digest(source),
        ],
        cwd=directory,
        env={**os.environ, "PYTHONPATH": str(source)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        yield process, f"http://127.0.0.1:{port}"
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


async def ready(client, process):
    for _ in range(200):
        if process.poll() is not None:
            raise RuntimeError("Benchmark server failed to start.")
        try:
            response = await client.get("/health")
            if response.status_code == 200 and response.json()["research_enabled"] is False:
                return
        except httpx.TransportError:
            pass
        await asyncio.sleep(0.025)
    raise RuntimeError("Benchmark server did not become healthy.")


def summary(durations, seconds):
    ordered = sorted(durations)
    return {
        "requests": len(ordered),
        "p50_ms": statistics.median(ordered),
        "p95_ms": ordered[math.ceil(0.95 * len(ordered)) - 1],
        "max_ms": ordered[-1],
        "requests_per_second": len(ordered) / seconds,
        "elapsed_seconds": seconds,
        "errors": 0,
    }


async def scenario(client, name, size, samples, warmup, concurrency):
    rng = random.Random(42)
    width = concurrency if name.startswith("concurrent_") else 1
    created = set()
    durations = []

    async def operation(index, phase):
        selected = rng.randrange(size)
        if name in ("saved_read", "saved_duplicate"):
            payload = fixture(selected)
        else:
            key = index // width if name == "concurrent_duplicate" else index
            payload = {"claim": f"Synthetic {name} {phase} claim {key}.", "context": {}}
        start = time.perf_counter()
        if name == "saved_read":
            response = await client.get(f"/investigations/{identity(selected)}")
        else:
            response = await client.post("/investigations", json=payload)
        elapsed = (time.perf_counter() - start) * 1000
        expected = 200 if name in ("saved_read", "saved_duplicate") else 202
        if response.status_code != expected:
            raise AssertionError(f"{name}: HTTP {response.status_code}, expected {expected}")
        data = response.json()
        assert data["claim"] == payload["claim"] and data["context"] == payload["context"]
        assert data["result"] is None
        if expected == 200:
            assert data["id"] == identity(selected) and data["reused"]
            assert data["status"] == "failed"
            assert datetime.fromisoformat(data["created_at"]) == datetime.fromisoformat(STAMP)
        else:
            assert data["status"] == "queued"
            if not data["reused"]:
                assert data["id"] not in created
                created.add(data["id"])
            if name != "concurrent_duplicate":
                assert not data["reused"]
        return elapsed, data

    measured_seconds = 0
    for phase, count in (("warmup", warmup), ("measured", samples)):
        start = time.perf_counter()
        for offset in range(0, count, width):
            batch = await asyncio.gather(
                *[operation(index, phase) for index in range(offset, offset + width)]
            )
            if name == "concurrent_duplicate":
                assert len({data["id"] for _, data in batch}) == 1
                assert sum(not data["reused"] for _, data in batch) == 1
                assert len({data["created_at"] for _, data in batch}) == 1
            if phase == "measured":
                durations.extend(elapsed for elapsed, _ in batch)
        if phase == "measured":
            measured_seconds = time.perf_counter() - start
    return summary(durations, measured_seconds), durations, len(created)


def verify_database(path, seeded, created):
    with sqlite3.connect(path) as db:
        for table in ("claim_requests", "investigations"):
            assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == seeded + created
        assert db.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 2 * seeded + created
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
        assert db.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert not db.execute("""SELECT i.id FROM investigations i LEFT JOIN events e
            ON e.investigation_id = i.id WHERE i.status = 'queued' GROUP BY i.id
            HAVING COUNT(e.sequence) != 1 OR MIN(e.type) != 'investigation_queued'""").fetchall()


async def benchmark(args):
    variants = []
    for item in args.variant or [f"current={ROOT / 'src'}"]:
        label, source = item.split("=", 1)
        source = await asyncio.to_thread(Path(source).resolve)
        if not (source / "aletheia/storage.py").is_file():
            raise ValueError("Variant must reference an Aletheia src directory.")
        variants.append((label, source))
    if len({label for label, _ in variants}) != len(variants):
        raise ValueError("Variant labels must be unique.")
    output = {
        "measured_at_utc": datetime.now(UTC).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "os": platform.system(),
            "os_release": platform.release(),
            "machine": platform.machine(),
            "sqlite": sqlite3.sqlite_version,
            "packages": {key: version(key) for key in ("aiosqlite", "fastapi", "httpx", "uvicorn")},
        },
        "parameters": {
            "sizes": args.sizes,
            "samples": args.samples,
            "warmup": args.warmup,
            "concurrency": args.concurrency,
            "repetitions": args.repetitions,
        },
        "variants": {label: {"source_sha256": source_digest(source)} for label, source in variants},
        "runs": [],
        "summary": [],
    }
    pooled = {}
    for repetition in range(args.repetitions):
        order = variants if repetition % 2 == 0 else list(reversed(variants))
        for size in args.sizes:
            for label, source in order:
                with tempfile.TemporaryDirectory(prefix="aletheia-benchmark-") as temporary:
                    directory = Path(temporary)
                    await seed(directory / "bench.db", size)
                    total_created = 0
                    with server(directory, source) as (process, base_url):
                        async with httpx.AsyncClient(
                            base_url=base_url,
                            trust_env=False,
                            timeout=15,
                            limits=httpx.Limits(
                                max_connections=args.concurrency,
                                max_keepalive_connections=args.concurrency,
                            ),
                        ) as client:
                            await ready(client, process)
                            for name in SCENARIOS:
                                with sqlite3.connect(directory / "bench.db") as db:
                                    starting_rows = db.execute(
                                        "SELECT COUNT(*) FROM investigations"
                                    ).fetchone()[0]
                                stats, durations, created = await scenario(
                                    client,
                                    name,
                                    size,
                                    args.samples,
                                    args.warmup,
                                    args.concurrency,
                                )
                                total_created += created
                                output["runs"].append(
                                    {
                                        "variant": label,
                                        "seeded_rows": size,
                                        "starting_rows": starting_rows,
                                        "repetition": repetition + 1,
                                        "scenario": name,
                                        **stats,
                                    }
                                )
                                key = (label, size, name)
                                samples, seconds = pooled.setdefault(key, ([], []))
                                samples.extend(durations)
                                seconds.append(stats["elapsed_seconds"])
                    verify_database(directory / "bench.db", size, total_created)
                    print(
                        f"PASS: {label}, {size} saved records, repetition {repetition + 1}",
                        flush=True,
                    )
    for (label, size, name), (durations, seconds) in pooled.items():
        output["summary"].append(
            {
                "variant": label,
                "seeded_rows": size,
                "scenario": name,
                **summary(durations, sum(seconds)),
            }
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    print(f"Results saved to {args.output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=[100, 1000, 10000])
    parser.add_argument("--samples", type=int, default=120)
    parser.add_argument("--warmup", type=int, default=16)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--variant", action="append", help="label=/absolute/path/to/src")
    parser.add_argument("--output", type=Path, default=Path("benchmark-results.json"))
    parser.add_argument("--serve", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--expected-source", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.serve:
        import uvicorn

        import aletheia
        from aletheia.api import create_app
        from aletheia.config import Settings

        if source_digest(Path(aletheia.__file__).resolve().parents[1]) != args.expected_source:
            raise RuntimeError("Server imported a different source variant than requested.")
        uvicorn.run(
            create_app(Settings(database_path=args.serve, queue_limit=10000)),
            host="127.0.0.1",
            port=args.port,
            workers=1,
            access_log=False,
        )
        return
    if (
        args.samples < 1
        or args.warmup < 1
        or args.repetitions < 1
        or args.concurrency < 1
        or min(args.sizes) < 1
        or args.samples % args.concurrency
        or args.warmup % args.concurrency
        or 3 * (args.samples + args.warmup) > 10000
    ):
        parser.error(
            "Use positive sizes/counts; samples and warmup must be divisible by concurrency, "
            "and 3*(samples+warmup) must not exceed queue capacity 10000."
        )
    asyncio.run(benchmark(args))


if __name__ == "__main__":
    main()
