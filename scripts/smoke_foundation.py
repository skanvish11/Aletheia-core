"""Opt-in localhost HTTP walkthrough; no providers, credentials, or real dotenv files."""

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def server(directory: Path, port: int):
    environment = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "ALETHEIA_DATABASE_PATH": str(directory / "smoke.sqlite3"),
        "ALETHEIA_QUEUE_LIMIT": "100",
        "ALETHEIA_MAX_BODY_BYTES": "65536",
    }
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "aletheia.api:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-access-log",
        ],
        cwd=directory,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        yield process
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def main():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    opener = build_opener(ProxyHandler({}))

    def request(path, payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        req = Request(
            f"http://127.0.0.1:{port}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with opener.open(req, timeout=2) as response:
            return response.status, json.load(response)

    def ready(process):
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError("Local server failed to start.")
            try:
                status, health = request("/health")
                assert status == 200 and health["research_enabled"] is False
                return
            except (URLError, TimeoutError):
                time.sleep(0.05)
        raise RuntimeError("Local server startup timed out.")

    with tempfile.TemporaryDirectory(prefix="aletheia-local-smoke-") as directory:
        payload = {
            "claim": "Mount Everest is above sea level.",
            "context": {"notes": "Foundation walkthrough"},
        }
        with server(Path(directory), port) as process:
            ready(process)
            status, first = request("/investigations", payload)
            assert status == 202 and first["status"] == "queued" and not first["reused"]
            assert first["result"] is None
            status, saved = request(first["links"]["self"])
            assert status == 200 and saved == {**first, "reused": True}
            status, repeated = request("/investigations", payload)
            assert status == 202 and repeated == saved
            print("PASS: health, submit, retrieve, and repeat submission over localhost HTTP")
        with server(Path(directory), port) as process:
            ready(process)
            status, reopened = request(first["links"]["self"])
            assert status == 200 and reopened == saved
            print("PASS: new server process preserves the same record, status, and timestamps")


if __name__ == "__main__":
    main()
