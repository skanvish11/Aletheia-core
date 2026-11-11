import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from research_fixtures import Providers
from test_research_pipeline import running, submit

from aletheia.claims import route
from aletheia.comparison import fingerprint
from aletheia.contracts import InvestigationRequest
from aletheia.evidence import admit, excerpts, snapshot
from aletheia.planning import validate_plan
from aletheia.research_contracts import Assertion, Assessment, SearchPlan, Snapshot
from aletheia.storage import Conflict, Storage, StorageError
from aletheia.verdicts import finding


def source(
    text=(
        "One sentence. Another sentence.\n- A list item. Still one block.\n"
        "| Year | Value |\nLast paragraph."
    ),
):
    return snapshot(
        url="https://source.test/record#fragment",
        title="Record",
        published_date=None,
        retrieved_at=datetime.now(UTC),
        text=text,
    )


def judgment(s, **overrides):
    values = dict(
        citation={"snapshot_id": s.id, "span_ids": [1]},
        relation="supports",
        scope_match=True,
        authoritative_record=True,
        credible_synthesis=False,
        synthesis_coverage=None,
        publisher=None,
        origin=None,
        independence="unknown",
        provenance_span_ids=[],
        provenance_note=None,
        rationale="Direct record.",
        limitations=[],
        flags=[],
    )
    values.update(overrides)
    return Assessment(**values)


def test_snapshot_spans_and_nonadjacent_quotes_are_exact():
    s = source()
    assert s.canonical_url == "https://source.test/record"
    assert [span.kind for span in s.spans] == ["sentence", "sentence", "block", "block", "sentence"]
    for span in s.spans:
        assert s.normalized_text[span.start : span.end] == span.text
    quotes = excerpts(s, [1, 2, 5], {1, 2, 3, 4, 5})
    assert [q.text for q in quotes] == ["One sentence. Another sentence.", "Last paragraph."]
    assert quotes[0].end <= quotes[1].start
    assert s.original_text == source().original_text
    changed = source("One\t\t sentence.\r\nA second line.")
    assert changed.normalized_text == "One sentence.\nA second line."
    assert changed.original_text != changed.normalized_text


@pytest.mark.parametrize("ids", [[1, 1], [2, 1], [0], [999], [], [3]])
def test_bad_or_unsupplied_spans_rejected(ids):
    with pytest.raises(ValueError):
        excerpts(source(), ids, {1, 2})


def test_snapshot_identity_and_provenance_validation():
    s = source()
    with pytest.raises(ValueError):
        admit(judgment(s, citation={"snapshot_id": "another", "span_ids": [1]}), s, {1})
    with pytest.raises(ValueError):
        admit(judgment(s, independence="established", origin="a study"), s, {1})
    with pytest.raises(ValueError):
        admit(judgment(s, credible_synthesis=True), s, {1})
    with pytest.raises(ValueError):
        admit(judgment(s, provenance_span_ids=[2]), s, {1})


@pytest.mark.parametrize(
    ("kind", "consequential", "recommended", "expected"),
    [
        ("direct_record", False, "quick", "quick"),
        ("direct_record", True, "quick", "deep"),
        ("direct_record", False, "deep", "deep"),
        ("causal", False, "quick", "deep"),
        ("generalized", False, "quick", "deep"),
    ],
)
def test_routing_never_downgrades(kind, consequential, recommended, expected):
    assertion = Assertion(
        text="A scoped claim", kind=kind, consequential=consequential, recommended_route=recommended
    )
    assert route(assertion)[0] == expected


def test_query_validation_cannot_be_bypassed_by_whitespace_or_followups():
    plan = SearchPlan(
        queries=[{"assertion_id": "a1", "text": " Duplicate  Query ", "purpose": "support"}],
        gap="A gap",
    )
    with pytest.raises(ValueError):
        validate_plan(plan, {"duplicate query"}, False)
    with pytest.raises(ValueError):
        validate_plan(plan, set(), True)
    plan.gap = None
    with pytest.raises(ValueError):
        validate_plan(plan, set(), False)


def test_unknown_shared_and_duplicate_origins_do_not_meet_deep_bar():
    s1, s2 = source("Same body."), source("Same body.")
    assertion = Assertion(
        text="A scoped claim", kind="causal", consequential=False, recommended_route="deep"
    )
    a1 = judgment(
        s1,
        independence="established",
        origin="Study One",
        provenance_span_ids=[1],
        provenance_note="Own measurement.",
    )
    a2 = judgment(
        s2,
        independence="established",
        origin="Study Two",
        provenance_span_ids=[1],
        provenance_note="Own measurement.",
    )
    e1, e2 = admit(a1, s1, {1}), admit(a2, s2, {1})
    computed, _ = finding(assertion, "deep", [e1, e2], [s1, s2])
    assert computed.verdict is None  # two URLs, identical extracted content
    s2 = source("Different body.")
    a2 = judgment(
        s2,
        independence="established",
        origin="  STUDY one ",
        provenance_span_ids=[1],
        provenance_note="Same study.",
    )
    e2 = admit(a2, s2, {1})
    assert finding(assertion, "deep", [e1, e2], [s1, s2])[0].verdict is None
    a2.origin = "Study Two"
    e2 = admit(a2, s2, {1})
    assert finding(assertion, "deep", [e1, e2], [s1, s2])[0].verdict == "true"


def test_fingerprint_excludes_run_ids_and_relation_but_includes_context_and_provenance():
    first = source("Same quote. Surrounding context.")
    second = source("Same quote. Surrounding context.")
    e1 = admit(judgment(first), first, {1})
    e2 = admit(judgment(second, relation="contradicts"), second, {1})
    assert fingerprint([first], [e1]) == fingerprint([second], [e2])
    second.published_date = "2001-01-01"
    assert fingerprint([first], [e1]) != fingerprint([second], [e2])
    third = source("Same quote. Changed context.")
    e3 = admit(judgment(third), third, {1})
    assert e1.excerpts[0].quote_hash == e3.excerpts[0].quote_hash
    assert fingerprint([first], [e1]) != fingerprint([third], [e3])
    assert fingerprint([], []) is None
    second = first.model_copy(deep=True)
    second.normalization_version = "different-version"
    assert fingerprint([first], [e1]) != fingerprint([second], [e1])


async def test_atomic_completion_rollback_and_append_only_records(settings):
    async with running(settings, Providers()) as (app, client):
        saved = await submit(client)
        template = (await app.state.storage.get(UUID(saved["id"]))).result
    store = Storage(settings.database_path)
    pending = await store.submit(InvestigationRequest(claim="Atomic completion"))
    claimed = await store.claim_next()
    assert claimed.id == pending.id
    async with store.connection() as db:
        await db.execute("""CREATE TRIGGER reject_terminal BEFORE INSERT ON events
            WHEN NEW.type='investigation_completed'
            BEGIN SELECT RAISE(ABORT, 'synthetic-secret'); END""")
    before = await store.events(claimed.id)
    with pytest.raises(StorageError):
        await store.finish(claimed.id, status="completed", result=template)
    assert (await store.get(claimed.id)).status == "running"
    assert (await store.get(claimed.id)).result is None
    assert await store.events(claimed.id) == before
    async with store.connection() as db:
        await db.execute("DROP TRIGGER reject_terminal")
    s = source()
    await store.save_records(claimed.id, "snapshot", [s])
    with pytest.raises(StorageError):
        await store.save_records(
            claimed.id, "snapshot", [s.model_copy(update={"original_text": "Changed"})]
        )
    assert (await store.records(claimed.id, "snapshot", Snapshot))[
        0
    ].original_text == s.original_text
    await store.finish(claimed.id, status="completed", result=template)
    assert (await store.events(claimed.id))[-1].type == "investigation_completed"
    with pytest.raises(Conflict):
        await store.finish(claimed.id, status="completed", result=template)
    with pytest.raises(Conflict):
        await store.save_records(claimed.id, "snapshot", [source()])


@pytest.mark.parametrize("failed_parent", [False, True])
async def test_refresh_transaction_failure_and_independent_connections(settings, failed_parent):
    async with running(settings, Providers(authentication_failure=failed_parent)) as (app, client):
        saved = await submit(client)
    store = Storage(settings.database_path)
    parent_id = UUID(saved["id"])
    async with store.connection() as db:
        await db.execute("""CREATE TRIGGER reject_refresh BEFORE INSERT ON events
            WHEN NEW.type='investigation_queued'
            BEGIN SELECT RAISE(ABORT, 'synthetic-secret'); END""")
    with pytest.raises(StorageError):
        await store.refresh(parent_id, "retry")
    async with store.connection() as db:
        assert (await (await db.execute("SELECT COUNT(*) FROM idempotency_keys")).fetchone())[
            0
        ] == 0
        assert (await (await db.execute("SELECT COUNT(*) FROM investigations")).fetchone())[0] == 1
        await db.execute("DROP TRIGGER reject_refresh")
    stores = [Storage(settings.database_path) for _ in range(8)]
    refreshed = await asyncio.gather(*[s.refresh(parent_id, "retry") for s in stores])
    assert len({r.id for r in refreshed}) == 1
    assert sum(not r.reused for r in refreshed) == 1
    claimed = await asyncio.gather(*[s.claim_next() for s in stores])
    assert sum(c is not None for c in claimed) == 1
    assert (await store.events(refreshed[0].id))[-1].type == "investigation_started"
    with pytest.raises(Conflict):
        await store.refresh(uuid4(), "retry")


async def test_migration_v1_preserves_claims_and_is_transactional(tmp_path, monkeypatch):
    import aiosqlite

    from aletheia.storage import SCHEMA

    path = tmp_path / "v1.sqlite3"
    async with aiosqlite.connect(path) as db:
        for statement in SCHEMA:
            await db.execute(statement)
        await db.execute("PRAGMA user_version=1")
        await db.commit()
    old = Storage(path)
    # Simulate the V1 reader before initializing the current research record projection.
    with monkeypatch.context() as legacy:
        legacy.setattr(
            "aletheia.storage.SELECT_INVESTIGATION",
            """
            SELECT i.*, c.original_claim, c.context_json,
            NULL AS analysis_json, NULL AS method_json
            FROM investigations i JOIN claim_requests c ON c.id=i.claim_request_id
        """,
        )
        original = await old.submit(InvestigationRequest(claim="A V1 queued claim"))
    await old.initialize()
    assert await old.get(original.id) == original.model_copy(update={"reused": True})
    async with old.connection() as db:
        assert (await (await db.execute("PRAGMA user_version")).fetchone())[0] == 3
        assert (await (await db.execute("SELECT COUNT(*) FROM research_records")).fetchone())[
            0
        ] == 0
    await old.initialize()
    assert len(await old.events(original.id)) == 1


async def test_refresh_rejects_active_and_bad_requests_and_events_validate_cursor(settings):
    from httpx import ASGITransport, AsyncClient

    from aletheia.api import create_app

    app = create_app(settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        saved = (await client.post("/investigations", json={"claim": "Queued"})).json()
        path = saved["links"]["self"]
        assert (
            await client.post(path + "/refresh", headers={"Idempotency-Key": "key"})
        ).status_code == 409
        assert (await client.post(path + "/refresh")).status_code == 422
        assert (
            await client.post(
                path + "/refresh", headers={"Idempotency-Key": "key"}, json={"claim": "other"}
            )
        ).status_code == 422
        assert (
            await client.get(path + "/events", headers={"Last-Event-ID": "-1"})
        ).status_code == 422
        assert (await client.get(path + "/events?after=-1")).status_code == 422
        for suffix in ("evidence", "comparison", "events"):
            assert (await client.get(f"/investigations/{uuid4()}/{suffix}")).status_code == 404


async def test_failed_migration_rolls_back_schema_and_version(tmp_path, monkeypatch):
    import aiosqlite

    from aletheia.storage import RESEARCH_SCHEMA, SCHEMA

    path = tmp_path / "migration.sqlite3"
    async with aiosqlite.connect(path) as db:
        for statement in SCHEMA:
            await db.execute(statement)
        await db.execute("PRAGMA user_version=1")
        await db.commit()
    monkeypatch.setattr("aletheia.storage.RESEARCH_SCHEMA", (RESEARCH_SCHEMA[0], "INVALID SQL"))
    with pytest.raises(StorageError):
        await Storage(path).initialize()
    async with aiosqlite.connect(path) as db:
        assert (await (await db.execute("PRAGMA user_version")).fetchone())[0] == 1
        assert (
            await (
                await db.execute("SELECT name FROM sqlite_schema WHERE name='research_records'")
            ).fetchall()
            == []
        )
    monkeypatch.setattr("aletheia.storage.RESEARCH_SCHEMA", RESEARCH_SCHEMA)
    await Storage(path).initialize()


async def test_refresh_retrieval_failure_is_not_reported_as_deleted(settings):
    providers = Providers()
    async with running(settings, providers) as (_, client):
        saved = await submit(client)
        providers.options["extraction_failure"] = True
        response = await client.post(
            saved["links"]["self"] + "/refresh", headers={"Idempotency-Key": "failure"}
        )
        from research_fixtures import terminal

        refreshed = await terminal(client, response.json()["id"])
        comparison = (await client.get(refreshed["links"]["self"] + "/comparison")).json()
        assert comparison["sources"][0]["change"] == "retrieval_failed"
        assert comparison["same_relevant_evidence"] is False
        assert comparison["consistency_status"] == "not_comparable"


def test_narrow_scope_is_context_not_support_for_a_broader_claim():
    s = source()
    flag = {"type": "narrow_scope", "dimension": "population", "explanation": "Only adults."}
    with pytest.raises(ValueError, match="Narrower evidence"):
        admit(judgment(s, flags=[flag]), s, {1})
    contextual = admit(judgment(s, flags=[flag], relation="context", scope_match=False), s, {1})
    assertion = Assertion(
        text="All populations", kind="generalized", consequential=False, recommended_route="deep"
    )
    computed, dropped = finding(assertion, "deep", [contextual], [s])
    assert computed.verdict is None
    assert computed.qualification_flags[0].dimension == "population"
    assert not dropped
