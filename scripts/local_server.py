"""Disposable localhost server for development checks; no dotenv or provider access."""

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4


def source_digest(source):
    digest = hashlib.sha256()
    for file in sorted((source / "aletheia").glob("*.py")):
        digest.update(file.name.encode())
        digest.update(file.read_bytes())
    return digest.hexdigest()


@contextmanager
def server(directory, source, database_name, queue_limit=100):
    address_file = directory / f"server-{uuid4()}.json"
    process = subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--database",
            str(directory / database_name),
            "--address-file",
            str(address_file),
            "--queue-limit",
            str(queue_limit),
            "--expected-source",
            source_digest(source),
        ],
        cwd=directory,
        env={**os.environ, "PYTHONPATH": str(source)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(200):
            if process.poll() is not None:
                raise RuntimeError("Local server failed to start.")
            if address_file.exists():
                port = json.loads(address_file.read_text())["port"]
                yield process, f"http://127.0.0.1:{port}"
                return
            time.sleep(0.05)
        raise RuntimeError("Local server did not publish its address.")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        address_file.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--address-file", type=Path, required=True)
    parser.add_argument("--queue-limit", type=int, required=True)
    parser.add_argument("--expected-source", required=True)
    args = parser.parse_args()

    import uvicorn

    import aletheia
    from aletheia.api import create_app
    from aletheia.config import Settings

    if source_digest(Path(aletheia.__file__).resolve().parents[1]) != args.expected_source:
        raise RuntimeError("Server imported a different source variant than requested.")
    app = create_app(Settings(database_path=args.database, queue_limit=args.queue_limit))
    # The child binds port 0 once and retains this socket throughout its lifetime.
    # There is no release/rebind window, and each restart publishes a fresh address.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        temporary = args.address_file.with_suffix(".tmp")
        temporary.write_text(json.dumps({"port": listener.getsockname()[1]}))
        temporary.replace(args.address_file)
        server_instance = uvicorn.Server(uvicorn.Config(app, access_log=False))
        server_instance.run(sockets=[listener])


if __name__ == "__main__":
    main()
