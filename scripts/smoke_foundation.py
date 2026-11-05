"""Opt-in localhost HTTP walkthrough; no providers, credentials, or real dotenv files."""

import json
import tempfile
import time
from http.client import RemoteDisconnected
from pathlib import Path
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener

from local_server import server

ROOT = Path(__file__).resolve().parents[1]


def ready(process, request):
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError("Local server failed to start.")
        try:
            status, health = request("/health")
            assert status == 200 and health["research_enabled"] is False
            return
        except (URLError, TimeoutError, RemoteDisconnected, ConnectionError):
            time.sleep(0.05)
    raise RuntimeError("Local server startup timed out.")


def main():
    opener = build_opener(ProxyHandler({}))

    def request(path, payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        req = Request(
            f"{base_url}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with opener.open(req, timeout=2) as response:
            return response.status, json.load(response)

    with tempfile.TemporaryDirectory(prefix="aletheia-local-smoke-") as directory:
        payload = {
            "claim": "Mount Everest is above sea level.",
            "context": {"notes": "Foundation walkthrough"},
        }
        with server(Path(directory), ROOT / "src", "smoke.sqlite3") as (process, base_url):
            ready(process, request)
            status, first = request("/investigations", payload)
            assert status == 202 and first["status"] == "queued" and not first["reused"]
            assert first["result"] is None
            status, saved = request(first["links"]["self"])
            assert status == 200 and saved == {**first, "reused": True}
            status, repeated = request("/investigations", payload)
            assert status == 202 and repeated == saved
            print("PASS: health, submit, retrieve, and repeat submission over localhost HTTP")
        with server(Path(directory), ROOT / "src", "smoke.sqlite3") as (process, base_url):
            ready(process, request)
            status, reopened = request(first["links"]["self"])
            assert status == 200 and reopened == saved
            print("PASS: new server process preserves the same record, status, and timestamps")


if __name__ == "__main__":
    main()
