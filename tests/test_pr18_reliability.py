"""Diagnostic failures must preserve paid results, original errors, and shutdown."""

import asyncio
import json
from uuid import UUID

import httpx
import pytest
from research_fixtures import Providers, terminal
from test_providers import Answer, budget, completion, generate
from test_providers import settings as provider_settings
from test_research_pipeline import running, submit

from aletheia.providers.errors import ErrorCode, ProviderError
from aletheia.providers.nebius import NebiusProvider
from aletheia.storage import Conflict, StorageError
from aletheia.tasks import Tasks


@pytest.mark.parametrize("failure", [StorageError, Conflict])
@pytest.mark.parametrize("status", [200, 401])
async def test_diagnostic_failure_preserves_provider_result_and_error(failure, status, caplog):
    allowance = budget()

    async def fail(event, payload):
        raise failure("private-diagnostic-secret")

    allowance.observer = fail
    async with NebiusProvider(
        provider_settings(),
        transport=httpx.MockTransport(lambda r: httpx.Response(status, json=completion())),
    ) as model:
        if status == 200:
            assert (await generate(model, allowance)).value.year == 2023
        else:
            with pytest.raises(ProviderError) as caught:
                await generate(model, allowance)
            assert caught.value.code == ErrorCode.AUTHENTICATION
    assert allowance.used["model"] == 1
    assert allowance.attempts[0].outcome == ("success" if status == 200 else "authentication")
    assert "could not be saved" in caplog.text
    assert "private-diagnostic-secret" not in caplog.text


@pytest.mark.parametrize("failure", [StorageError, Conflict])
@pytest.mark.parametrize("status", [200, 401])
async def test_task_diagnostic_failure_preserves_result_and_error(failure, status, caplog):
    async def emit(event, payload):
        raise failure("private-task-secret")

    async with NebiusProvider(
        provider_settings(),
        transport=httpx.MockTransport(lambda r: httpx.Response(status, json=completion())),
    ) as model:
        tasks = Tasks(model, budget(), emit)
        if status == 200:
            result = await tasks.call("test", "Return year", {}, Answer, lambda value: None)
            assert result.year == 2023
        else:
            with pytest.raises(ProviderError) as caught:
                await tasks.call("test", "Return year", {}, Answer, lambda value: None)
            assert caught.value.code == ErrorCode.AUTHENTICATION
    assert "private-task-secret" not in caplog.text


async def test_cancelled_provider_and_task_skip_diagnostic_writes():
    entered = asyncio.Event()
    records = []
    allowance = budget()

    async def hold(request):
        entered.set()
        await asyncio.Event().wait()

    async def emit(event, payload):
        # A write after cancellation would both delay shutdown and mask the cancellation.
        if asyncio.current_task().cancelling():
            records.append("write_during_cancellation")
            raise StorageError("private-cancellation-secret")
        records.append(event)

    allowance.observer = emit
    async with NebiusProvider(provider_settings(), transport=httpx.MockTransport(hold)) as model:
        tasks = Tasks(model, allowance, emit)
        work = asyncio.create_task(tasks.call("test", "Return year", {}, Answer, lambda v: None))
        await asyncio.wait_for(entered.wait(), 1)
        work.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(work, 1)
    assert records == ["task_started", "provider_attempt_started"]
    assert allowance.attempts[0].outcome == "cancelled"


async def test_cancellation_during_diagnostic_write_is_not_suppressed():
    entered = asyncio.Event()
    allowance = budget()

    async def hold(event, payload):
        if event == "provider_attempt_finished":
            entered.set()
            await asyncio.Event().wait()

    allowance.observer = hold
    async with NebiusProvider(
        provider_settings(),
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=completion())),
    ) as model:
        work = asyncio.create_task(generate(model, allowance))
        await asyncio.wait_for(entered.wait(), 1)
        work.cancel()
        with pytest.raises(asyncio.CancelledError):
            await work
    assert allowance.attempts[0].outcome == "success"


@pytest.mark.parametrize("auth_failure", [False, True])
async def test_diagnostic_storage_failures_preserve_durable_terminal_state(
    settings, monkeypatch, auth_failure, caplog
):
    providers = Providers(authentication_failure=auth_failure)
    async with running(settings, providers) as (app, client):
        original = app.state.storage.progress

        async def fail_diagnostics(investigation_id, event, payload, **kwargs):
            if event.startswith(("provider_", "task_")) or event == "research_stopped":
                raise StorageError("private-db-secret")
            return await original(investigation_id, event, payload, **kwargs)

        monkeypatch.setattr(app.state.storage, "progress", fail_diagnostics)
        saved = await submit(client)
        assert saved["status"] == ("failed" if auth_failure else "completed")
        trace = await app.state.storage.events(UUID(saved["id"]))
        assert trace[-1].type == (
            "investigation_failed" if auth_failure else "investigation_completed"
        )
        if not auth_failure:
            assert saved["result"]["verdict"] == "true"
        path = saved["links"]["self"]
        replay = (await client.get(path + "/events")).text
    async with running(settings, Providers()) as (_, client):
        assert (await client.get(path)).json() == saved
        assert (await client.get(path + "/events")).text == replay
    assert "private-db-secret" not in caplog.text + replay


async def test_input_size_matches_unicode_prompt_and_attempt_event_is_unique(settings):
    providers = Providers()
    async with running(settings, providers) as (app, client):
        response = await client.post(
            "/investigations", json={"claim": "The Archive’s café opened in 2000. 世界"}
        )
        saved = await terminal(client, response.json()["id"])
        trace = await app.state.storage.events(UUID(saved["id"]))
        starts = [e for e in trace if e.type == "task_started"]
        assert int(starts[0].payload["input_chars"]) == len(
            json.dumps(providers.model_inputs[0][1], ensure_ascii=False)
        )
        assert not any(e.type == "model_attempt_finished" for e in trace)
        attempts = [e for e in trace if e.type == "provider_attempt_finished"]
        assert len(attempts) == len(providers.calls)


async def test_internal_error_survives_both_diagnostic_layers():
    original = RuntimeError("private-original-error")
    allowance = budget()

    async def broken_transport(request):
        raise original

    async def broken_diagnostic(event, payload):
        raise StorageError("private-secondary-error")

    allowance.observer = broken_diagnostic
    async with NebiusProvider(
        provider_settings(), transport=httpx.MockTransport(broken_transport)
    ) as model:
        tasks = Tasks(model, allowance, broken_diagnostic)
        with pytest.raises(RuntimeError) as caught:
            await tasks.call("test", "Return year", {}, Answer, lambda v: None)
    assert caught.value is original
    assert allowance.attempts[0].outcome == "internal_error"


@pytest.mark.parametrize("reason", ["research_deadline", "hard_deadline"])
async def test_budget_check_and_http_timeout_share_deadline_reason(reason):
    import time

    from aletheia.budgets import RunBudget

    allowance = RunBudget()

    async def timeout(request):
        allowance.deadline = time.monotonic() + (10 if reason == "research_deadline" else -1)
        raise httpx.ReadTimeout("private-timeout")

    async with NebiusProvider(provider_settings(), transport=httpx.MockTransport(timeout)) as model:
        with pytest.raises(ProviderError) as transport_error:
            await generate(model, allowance)
    with pytest.raises(ProviderError) as check_error:
        allowance.check("nebius", "model", 1)
    assert transport_error.value.code == check_error.value.code == ErrorCode.DEADLINE
    assert transport_error.value.limit_reason == check_error.value.limit_reason == reason
