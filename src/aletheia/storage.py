"""Transactional SQLite persistence, without provider calls or in-memory job state."""

import json
import sqlite3
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import aiosqlite

from aletheia.contracts import Investigation, InvestigationEvent, InvestigationRequest

SCHEMA_VERSION = 2
SCHEMA = (
    """CREATE TABLE claim_requests (
        id TEXT PRIMARY KEY, original_claim TEXT NOT NULL, context_json TEXT NOT NULL,
        request_key TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL
    )""",
    """CREATE TABLE investigations (
        id TEXT PRIMARY KEY, claim_request_id TEXT NOT NULL REFERENCES claim_requests(id),
        version INTEGER NOT NULL CHECK(version > 0),
        parent_id TEXT REFERENCES investigations(id),
        status TEXT NOT NULL CHECK(status IN
            ('queued','running','needs_clarification','completed','partial','failed')),
        stage TEXT, route TEXT, stop_reason TEXT,
        created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT,
        result_json TEXT, clarification_json TEXT, error_json TEXT,
        UNIQUE(claim_request_id, version)
    )""",
    """CREATE TABLE events (
        investigation_id TEXT NOT NULL REFERENCES investigations(id),
        sequence INTEGER NOT NULL CHECK(sequence > 0), timestamp TEXT NOT NULL,
        type TEXT NOT NULL, stage TEXT, payload_json TEXT NOT NULL,
        PRIMARY KEY(investigation_id, sequence)
    )""",
    "CREATE INDEX investigations_status ON investigations(status)",
)
RESEARCH_SCHEMA = (
    """CREATE TABLE research_records (
        investigation_id TEXT NOT NULL REFERENCES investigations(id),
        kind TEXT NOT NULL, record_id TEXT NOT NULL, payload_json TEXT NOT NULL,
        PRIMARY KEY(investigation_id, kind, record_id)
    )""",
    """CREATE TABLE idempotency_keys (
        key TEXT PRIMARY KEY, parent_id TEXT NOT NULL REFERENCES investigations(id),
        investigation_id TEXT NOT NULL REFERENCES investigations(id)
    )""",
)
SELECT_INVESTIGATION = """
    SELECT i.*, c.original_claim, c.context_json
    FROM investigations i JOIN claim_requests c ON c.id = i.claim_request_id
"""


class StorageError(Exception):
    """Safe database error; raw SQLite errors may contain private data."""


class Conflict(Exception):
    """Requested action conflicts with the persisted investigation state."""


class QueueFull(Exception):
    """No capacity for another distinct investigation."""


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class Storage:
    def __init__(self, path: Path, queue_limit: int = 100):
        self.path = path
        self.queue_limit = queue_limit

    @asynccontextmanager
    async def connection(self):
        try:
            async with aiosqlite.connect(self.path, isolation_level=None, timeout=5) as db:
                db.row_factory = aiosqlite.Row
                await db.execute("PRAGMA foreign_keys = ON")
                yield db
        except sqlite3.Error:
            raise StorageError("Database operation failed.") from None

    async def initialize(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            raise StorageError(
                "Database initialization failed; check its location and permissions."
            ) from None
        async with self.connection() as db:
            await db.execute("BEGIN IMMEDIATE")
            try:
                version = (await (await db.execute("PRAGMA user_version")).fetchone())[0]
                if version not in (0, 1, SCHEMA_VERSION):
                    raise StorageError(
                        "Unsupported database schema version; use a compatible application."
                    )
                schema = await (
                    await db.execute("SELECT sql FROM sqlite_schema WHERE name NOT GLOB 'sqlite_*'")
                ).fetchall()
                if version == 0:
                    if schema:
                        raise StorageError(
                            "Database is not empty; choose a new Aletheia database file."
                        )
                    for statement in SCHEMA + RESEARCH_SCHEMA:
                        await db.execute(statement)
                    await db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                elif {" ".join(row[0].split()) for row in schema} != {
                    " ".join(statement.split())
                    for statement in (SCHEMA if version == 1 else SCHEMA + RESEARCH_SCHEMA)
                }:
                    # Version alone does not establish ownership. Accept the original V1
                    # schema, including databases created before this guard was added.
                    raise StorageError(
                        "Database schema does not match Aletheia; no initialization performed."
                    )
                if version == 1:
                    for statement in RESEARCH_SCHEMA:
                        await db.execute(statement)
                    await db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                await db.commit()
            except BaseException:
                await db.rollback()
                raise
            await db.execute("PRAGMA journal_mode = WAL")
        await self.recover_interrupted()

    async def health(self) -> None:
        async with self.connection() as db:
            # Query actual application tables, not merely an open SQLite connection.
            await db.execute("SELECT id FROM claim_requests LIMIT 1")
            await db.execute("SELECT id FROM investigations LIMIT 1")
            await db.execute("SELECT sequence FROM events LIMIT 1")
            await db.execute("SELECT record_id FROM research_records LIMIT 1")
            await db.execute("SELECT key FROM idempotency_keys LIMIT 1")

    @staticmethod
    async def _append_event(
        db,
        investigation_id: str,
        event_type: str,
        timestamp: str,
        payload: dict,
        stage: str | None = None,
    ):
        # Call only inside the transaction that changes the investigation.
        await db.execute(
            """INSERT INTO events
               (investigation_id, sequence, timestamp, type, stage, payload_json)
               SELECT ?, COALESCE(MAX(sequence), 0) + 1, ?, ?, ?, ?
               FROM events WHERE investigation_id = ?""",
            (investigation_id, timestamp, event_type, stage, json.dumps(payload), investigation_id),
        )

    async def submit(self, request: InvestigationRequest) -> Investigation:
        async with self.connection() as db:
            await db.execute("BEGIN IMMEDIATE")
            try:
                row = await (
                    await db.execute(
                        SELECT_INVESTIGATION
                        + " WHERE c.request_key = ? ORDER BY i.version DESC LIMIT 1",
                        (request.request_key(),),
                    )
                ).fetchone()
                if row is not None:
                    result = self._record(row, reused=True)
                    await db.commit()
                    return result
                pending = (
                    await (
                        await db.execute(
                            "SELECT COUNT(*) FROM investigations "
                            "WHERE status IN ('queued', 'running')"
                        )
                    ).fetchone()
                )[0]
                if pending >= self.queue_limit:
                    raise QueueFull
                request_id, investigation_id, now = str(uuid4()), str(uuid4()), utc_now()
                await db.execute(
                    "INSERT INTO claim_requests VALUES (?, ?, ?, ?, ?)",
                    (
                        request_id,
                        request.claim,
                        json.dumps(request.context.supplied()),
                        request.request_key(),
                        now,
                    ),
                )
                await db.execute(
                    """INSERT INTO investigations
                       (id, claim_request_id, version, status, created_at)
                       VALUES (?, ?, 1, 'queued', ?)""",
                    (investigation_id, request_id, now),
                )
                await self._append_event(db, investigation_id, "investigation_queued", now, {})
                row = await (
                    await db.execute(SELECT_INVESTIGATION + " WHERE i.id = ?", (investigation_id,))
                ).fetchone()
                result = self._record(row, reused=False)
                await db.commit()
                return result
            except BaseException:
                await db.rollback()
                raise

    async def get(self, investigation_id: UUID) -> Investigation | None:
        async with self.connection() as db:
            row = await (
                await db.execute(SELECT_INVESTIGATION + " WHERE i.id = ?", (str(investigation_id),))
            ).fetchone()
            return self._record(row, reused=True) if row else None

    async def events(self, investigation_id: UUID) -> list[InvestigationEvent]:
        async with self.connection() as db:
            rows = await (
                await db.execute(
                    "SELECT * FROM events WHERE investigation_id = ? ORDER BY sequence",
                    (str(investigation_id),),
                )
            ).fetchall()
        return [
            InvestigationEvent(
                investigation_id=row["investigation_id"],
                sequence=row["sequence"],
                timestamp=row["timestamp"],
                type=row["type"],
                stage=row["stage"],
                payload=json.loads(row["payload_json"]),
            )
            for row in rows
        ]

    async def recover_interrupted(self) -> None:
        async with self.connection() as db:
            await db.execute("BEGIN IMMEDIATE")
            try:
                rows = await (
                    await db.execute("SELECT id FROM investigations WHERE status = 'running'")
                ).fetchall()
                for row in rows:
                    now = utc_now()
                    error = {"message": "Investigation interrupted by application shutdown."}
                    await db.execute(
                        """UPDATE investigations SET status = 'failed', stage = NULL,
                           stop_reason = 'interrupted', finished_at = ?, error_json = ?,
                           result_json = NULL WHERE id = ?""",
                        (now, json.dumps(error), row["id"]),
                    )
                    await self._append_event(
                        db, row["id"], "investigation_failed", now, {"stop_reason": "interrupted"}
                    )
                await db.commit()
            except BaseException:
                await db.rollback()
                raise

    async def claim_next(self) -> Investigation | None:
        async with self.connection() as db:
            await db.execute("BEGIN IMMEDIATE")
            try:
                row = await (
                    await db.execute(
                        SELECT_INVESTIGATION
                        + " WHERE i.status = 'queued' ORDER BY i.created_at, i.id LIMIT 1"
                    )
                ).fetchone()
                if row is None:
                    await db.commit()
                    return None
                now = utc_now()
                await db.execute(
                    "UPDATE investigations SET status='running', started_at=? WHERE id=?",
                    (now, row["id"]),
                )
                await self._append_event(db, row["id"], "investigation_started", now, {})
                claimed = await (
                    await db.execute(SELECT_INVESTIGATION + " WHERE i.id=?", (row["id"],))
                ).fetchone()
                await db.commit()
                return self._record(claimed, reused=False)
            except BaseException:
                await db.rollback()
                raise

    async def progress(self, investigation_id, event_type, payload, *, stage=None, route=None):
        # Reject unsafe/unbounded event shapes before committing.
        InvestigationEvent(
            investigation_id=investigation_id,
            sequence=1,
            timestamp=utc_now(),
            type=event_type,
            stage=stage,
            payload=payload,
        )
        async with self.connection() as db:
            await db.execute("BEGIN IMMEDIATE")
            try:
                row = await (
                    await db.execute(
                        "SELECT status FROM investigations WHERE id=?", (str(investigation_id),)
                    )
                ).fetchone()
                if not row or row[0] != "running":
                    raise Conflict("Investigation is not running.")
                await db.execute(
                    "UPDATE investigations SET stage=COALESCE(?,stage), "
                    "route=COALESCE(?,route) WHERE id=?",
                    (stage, route, str(investigation_id)),
                )
                await self._append_event(
                    db, str(investigation_id), event_type, utc_now(), payload, stage
                )
                await db.commit()
            except BaseException:
                await db.rollback()
                raise

    async def save_records(self, investigation_id, kind, records):
        # Append-only records: snapshots and span identities can never be regenerated in place.
        async with self.connection() as db:
            await db.execute("BEGIN IMMEDIATE")
            try:
                row = await (
                    await db.execute(
                        "SELECT status FROM investigations WHERE id=?", (str(investigation_id),)
                    )
                ).fetchone()
                if not row or row[0] != "running":
                    raise Conflict("Investigation is not running.")
                for record in records:
                    await db.execute(
                        "INSERT INTO research_records VALUES (?,?,?,?)",
                        (str(investigation_id), kind, record.id, record.model_dump_json()),
                    )
                await db.commit()
            except BaseException:
                await db.rollback()
                raise

    async def records(self, investigation_id, kind, model):
        async with self.connection() as db:
            rows = await (
                await db.execute(
                    "SELECT payload_json FROM research_records "
                    "WHERE investigation_id=? AND kind=? ORDER BY rowid",
                    (str(investigation_id), kind),
                )
            ).fetchall()
        return [model.model_validate_json(row[0]) for row in rows]

    async def finish(
        self,
        investigation_id,
        *,
        status,
        stop_reason=None,
        result=None,
        questions=None,
        error=None,
        comparison=None,
    ):
        if status not in {"completed", "partial", "failed", "needs_clarification"}:
            raise ValueError("Terminal status required.")
        if (status in {"completed", "partial"}) != (result is not None):
            raise ValueError("Completed and partial investigations require validated results.")
        if status == "needs_clarification" and not questions:
            raise ValueError("Clarification questions required.")
        event = {
            "completed": "investigation_completed",
            "partial": "investigation_partial",
            "failed": "investigation_failed",
            "needs_clarification": "clarification_required",
        }[status]
        async with self.connection() as db:
            await db.execute("BEGIN IMMEDIATE")
            try:
                row = await (
                    await db.execute(
                        "SELECT status FROM investigations WHERE id=?", (str(investigation_id),)
                    )
                ).fetchone()
                if not row or row[0] != "running":
                    raise Conflict("Investigation is not running.")
                now = utc_now()
                await db.execute(
                    """UPDATE investigations SET status=?, stage=NULL, stop_reason=?, finished_at=?,
                       result_json=?, clarification_json=?, error_json=? WHERE id=?""",
                    (
                        status,
                        stop_reason,
                        now,
                        result.model_dump_json() if result else None,
                        json.dumps(questions) if questions else None,
                        json.dumps({"message": error}) if error else None,
                        str(investigation_id),
                    ),
                )
                if comparison:
                    await db.execute(
                        "INSERT INTO research_records VALUES (?,?,?,?)",
                        (
                            str(investigation_id),
                            "comparison",
                            "comparison",
                            comparison.model_dump_json(),
                        ),
                    )
                    await self._append_event(
                        db, str(investigation_id), "comparison_completed", now, {}
                    )
                    if comparison.consistency_status == "inconsistent":
                        await self._append_event(
                            db, str(investigation_id), "consistency_flagged", now, {}
                        )
                await self._append_event(
                    db,
                    str(investigation_id),
                    event,
                    now,
                    {"stop_reason": stop_reason} if stop_reason else {},
                )
                await db.commit()
            except BaseException:
                await db.rollback()
                raise

    async def refresh(self, parent_id, key):
        async with self.connection() as db:
            await db.execute("BEGIN IMMEDIATE")
            try:
                used = await (
                    await db.execute("SELECT * FROM idempotency_keys WHERE key=?", (key,))
                ).fetchone()
                if used:
                    if used["parent_id"] != str(parent_id):
                        raise Conflict(
                            "Idempotency key was already used for another investigation."
                        )
                    row = await (
                        await db.execute(
                            SELECT_INVESTIGATION + " WHERE i.id=?", (used["investigation_id"],)
                        )
                    ).fetchone()
                    await db.commit()
                    return self._record(row, reused=True)
                parent = await (
                    await db.execute(SELECT_INVESTIGATION + " WHERE i.id=?", (str(parent_id),))
                ).fetchone()
                if parent is None:
                    await db.commit()
                    return None
                if parent["status"] not in {"completed", "partial"} or not parent["result_json"]:
                    raise Conflict(
                        "Refresh requires a completed or partial investigation with resolved scope."
                    )
                pending = (
                    await (
                        await db.execute(
                            "SELECT COUNT(*) FROM investigations "
                            "WHERE status IN ('queued','running')"
                        )
                    ).fetchone()
                )[0]
                if pending >= self.queue_limit:
                    raise QueueFull
                version = (
                    await (
                        await db.execute(
                            "SELECT MAX(version)+1 FROM investigations WHERE claim_request_id=?",
                            (parent["claim_request_id"],),
                        )
                    ).fetchone()
                )[0]
                investigation_id, now = str(uuid4()), utc_now()
                await db.execute(
                    """INSERT INTO investigations
                    (id, claim_request_id, version, parent_id, status, created_at)
                    VALUES (?,?,?,?,'queued',?)""",
                    (investigation_id, parent["claim_request_id"], version, str(parent_id), now),
                )
                await db.execute(
                    "INSERT INTO idempotency_keys VALUES (?,?,?)",
                    (key, str(parent_id), investigation_id),
                )
                await self._append_event(db, investigation_id, "investigation_queued", now, {})
                row = await (
                    await db.execute(SELECT_INVESTIGATION + " WHERE i.id=?", (investigation_id,))
                ).fetchone()
                await db.commit()
                return self._record(row, reused=False)
            except BaseException:
                await db.rollback()
                raise

    @staticmethod
    def _record(row, *, reused: bool) -> Investigation:
        return Investigation(
            id=row["id"],
            claim=row["original_claim"],
            context=json.loads(row["context_json"]),
            version=row["version"],
            parent_id=row["parent_id"],
            status=row["status"],
            stage=row["stage"],
            route=row["route"],
            stop_reason=row["stop_reason"],
            reused=reused,
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            result=json.loads(row["result_json"]) if row["result_json"] else None,
            clarification_questions=json.loads(row["clarification_json"])
            if row["clarification_json"]
            else None,
            error=json.loads(row["error_json"]) if row["error_json"] else None,
            links={
                "self": f"/investigations/{row['id']}",
                "events": f"/investigations/{row['id']}/events",
                "evidence": f"/investigations/{row['id']}/evidence",
                "comparison": f"/investigations/{row['id']}/comparison",
                "refresh": f"/investigations/{row['id']}/refresh"
                if row["status"] in {"completed", "partial"} and row["result_json"]
                else None,
            },
        )
