import importlib
import json
import sqlite3
from contextlib import closing
from http.client import RemoteDisconnected
from pathlib import Path
from threading import get_ident
from types import SimpleNamespace
from urllib.error import URLError

import pytest

from aletheia.config import Settings
from aletheia.contracts import InvestigationRequest
from aletheia.storage import SCHEMA, Storage, StorageError


@pytest.mark.parametrize("ensure_ascii", [False, True])
async def test_maximum_unicode_request_fits_default_body_limit(client, ensure_ascii):
    payload = {
        "claim": "😀" * 8000,
        "context": {key: "😀" * 4000 for key in ("timeframe", "location", "definitions", "notes")},
    }
    body = json.dumps(payload, ensure_ascii=ensure_ascii).encode()
    assert len(body) < Settings().max_body_bytes
    response = await client.post(
        "/investigations", content=body, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 202
    assert response.json()["claim"] == payload["claim"]
    assert response.json()["context"] == payload["context"]


async def test_total_body_limit_still_rejects_excess_whitespace(client):
    body = b'{"claim":"valid"}' + b" " * Settings().max_body_bytes
    response = await client.post(
        "/investigations", content=body, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413


def test_environment_uses_same_default_body_limit(monkeypatch):
    monkeypatch.setattr("aletheia.config.load_dotenv", lambda **kwargs: None)
    for name in ("ALETHEIA_MAX_BODY_BYTES", "ALETHEIA_DATABASE_PATH", "ALETHEIA_QUEUE_LIMIT"):
        monkeypatch.delenv(name, raising=False)
    assert Settings.from_environment().max_body_bytes == Settings().max_body_bytes == 327680


@pytest.mark.parametrize("version", [0, 1])
@pytest.mark.parametrize(
    "ddl",
    [
        "CREATE TABLE unrelated_app (id INTEGER PRIMARY KEY)",
        "CREATE TABLE events (private_data TEXT)",
        "CREATE VIEW unrelated_view AS SELECT 1",
        "CREATE TABLE sqliteuser (id INTEGER)",
    ],
)
async def test_foreign_database_rejected_without_changes(tmp_path, version, ddl):
    path = tmp_path / "foreign.db"
    with closing(sqlite3.connect(path)) as db, db:
        db.execute(ddl)
        db.execute(f"PRAGMA user_version = {version}")
    before = path.read_bytes()
    with pytest.raises(StorageError, match="not empty|does not match"):
        await Storage(path).initialize()
    assert path.read_bytes() == before
    assert not path.with_name(path.name + "-wal").exists()


async def test_original_v1_database_is_accepted(tmp_path):
    path = tmp_path / "legacy.db"
    with closing(sqlite3.connect(path)) as db, db:
        for statement in SCHEMA:
            db.execute(statement)
        db.execute("PRAGMA user_version = 1")
    storage = Storage(path)
    await storage.initialize()
    original = await storage.submit(InvestigationRequest(claim="Existing V1 schema"))
    await storage.initialize()
    assert (await storage.get(original.id)).claim == original.claim


@pytest.fixture
def dev_scripts(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    return SimpleNamespace(
        smoke=importlib.import_module("smoke_foundation"),
        benchmark=importlib.import_module("benchmark_foundation"),
        mutation=importlib.import_module("check_test_sensitivity"),
    )


@pytest.mark.parametrize(
    "error",
    [
        URLError("synthetic failure"),
        TimeoutError(),
        RemoteDisconnected(),
        ConnectionResetError(),
        ConnectionAbortedError(),
    ],
)
def test_smoke_readiness_retries_transient_failures(dev_scripts, monkeypatch, error):
    attempts = []
    monkeypatch.setattr(dev_scripts.smoke.time, "sleep", lambda _: None)

    def request(path):
        attempts.append(path)
        if len(attempts) == 1:
            raise error
        return 200, {"research_enabled": False}

    dev_scripts.smoke.ready(SimpleNamespace(poll=lambda: None), request)
    assert attempts == ["/health", "/health"]


def test_smoke_readiness_is_bounded(dev_scripts, monkeypatch):
    attempts = []
    monkeypatch.setattr(dev_scripts.smoke.time, "sleep", lambda _: None)

    def request(path):
        attempts.append(path)
        raise ConnectionResetError()

    with pytest.raises(RuntimeError, match="timed out"):
        dev_scripts.smoke.ready(SimpleNamespace(poll=lambda: None), request)
    assert len(attempts) == 100


async def test_benchmark_sqlite_connections_close_even_on_failure(
    dev_scripts, monkeypatch, tmp_path
):
    opened = []
    connect = sqlite3.connect
    main_thread = get_ident()

    def track(*args, **kwargs):
        db = connect(*args, **kwargs)
        if get_ident() == main_thread:
            opened.append(db)
        return db

    monkeypatch.setattr(dev_scripts.benchmark.sqlite3, "connect", track)
    path = tmp_path / "bench.db"
    await dev_scripts.benchmark.seed(path, 3)
    dev_scripts.benchmark.verify_database(path, 3, 0)
    with pytest.raises(AssertionError):
        dev_scripts.benchmark.verify_database(path, 999, 0)
    assert len(opened) == 3
    for db in opened:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            db.execute("SELECT 1")


def test_mutation_changes_only_submission(dev_scripts):
    source = """class Storage:
    async def initialize(self):
        await db.rollback()
    async def submit(self, request):
        await db.rollback()
    async def recover_interrupted(self):
        await db.rollback()
"""
    changed = dev_scripts.mutation.mutate_submission(
        source, "await db.rollback()", "await db.commit()"
    )
    assert changed == source.replace(
        "async def submit(self, request):\n        await db.rollback()",
        "async def submit(self, request):\n        await db.commit()",
    )
    assert changed.count("await db.rollback()") == 2


@pytest.mark.parametrize("body", ["pass", "await db.rollback()\n        await db.rollback()"])
def test_mutation_rejects_missing_or_ambiguous_target(dev_scripts, body):
    source = f"class Storage:\n    async def submit(self, request):\n        {body}\n"
    with pytest.raises(ValueError, match="exactly once"):
        dev_scripts.mutation.mutate_submission(source, "await db.rollback()", "await db.commit()")
