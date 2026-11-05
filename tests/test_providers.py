"""Provider contracts, tested at the HTTP boundary with no external connections."""

import asyncio
import json
import time
import traceback
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest
from pydantic import BaseModel, ConfigDict, SecretStr

from aletheia.config import ConfigurationError
from aletheia.providers.common import CallBudget, ErrorCode, ProviderError, retry_delay
from aletheia.providers.nebius import NebiusProvider
from aletheia.providers.settings import ProviderSettings
from aletheia.providers.tavily import TavilyProvider

SECRET = "synthetic-secret-never-disclose"
URL_A = "https://example.org/a"
URL_B = "https://example.org/b"


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    year: int


def settings(**overrides):
    return ProviderSettings(
        **{
            "nebius_api_key": SECRET,
            "tavily_api_key": SECRET,
            "nebius_model": "fixture/model",
            "max_retries": 0,
            **overrides,
        }
    )


def budget(**overrides):
    return CallBudget(
        **{
            "model_attempts": 3,
            "search_attempts": 3,
            "extraction_attempts": 6,
            "deadline": time.monotonic() + 10,
            **overrides,
        }
    )


def completion(content='{"year": 2023}', finish="stop", **message):
    return {
        "choices": [
            {
                "message": {"role": "assistant", "content": content, **message},
                "finish_reason": finish,
            }
        ],
        "usage": {"prompt_tokens": 30, "completion_tokens": 8, "total_tokens": 38},
    }


async def generate(provider, allowance):
    return await provider.generate(
        instructions="Read the supplied record.",
        input_text="Published in 2023.",
        response_type=Answer,
        budget=allowance,
    )


async def test_nebius_wire_contract_and_validated_result():
    def handle(request):
        assert str(request.url) == "https://api.tokenfactory.nebius.com/v1/chat/completions"
        assert request.headers["authorization"] == f"Bearer {SECRET}"
        body = json.loads(request.content)
        assert body["model"] == "fixture/model"
        assert body["response_format"]["type"] == "json_schema"
        schema_format = body["response_format"]["json_schema"]
        assert schema_format["name"] == "aletheia_response" and schema_format["strict"] is True
        assert schema_format["schema"]["properties"]["year"]["type"] == "integer"
        assert body["stream"] is False and body["store"] is False
        assert body["max_tokens"] == 2048
        assert "JSON" in body["messages"][0]["content"]
        return httpx.Response(200, json=completion())

    allowance = budget()
    async with NebiusProvider(settings(), transport=httpx.MockTransport(handle)) as provider:
        result = await generate(provider, allowance)
    assert result.value.year == 2023
    assert result.usage.total_tokens == 38
    assert allowance.used["model"] == 1
    assert allowance.attempts[0].outcome == "success"
    assert allowance.attempts[0].elapsed_seconds >= 0


async def test_json_object_mode_still_validates_locally():
    def handle(request):
        assert json.loads(request.content)["response_format"] == {"type": "json_object"}
        return httpx.Response(200, json=completion('{"year":"2023"}'))

    async with NebiusProvider(
        settings(nebius_response_format="json_object"), transport=httpx.MockTransport(handle)
    ) as provider:
        with pytest.raises(ProviderError, match="invalid_response"):
            await generate(provider, budget())


@pytest.mark.parametrize(
    "payload,code",
    [
        (completion("not JSON " + SECRET), ErrorCode.INVALID_RESPONSE),
        (completion('{"year":"2023"}'), ErrorCode.INVALID_RESPONSE),
        (completion('{"year":2023,"extra":true}'), ErrorCode.INVALID_RESPONSE),
        (completion("{}"), ErrorCode.INVALID_RESPONSE),
        (completion('{"year": 2023, "year": 2024}'), ErrorCode.INVALID_RESPONSE),
        (completion('{"year": NaN}'), ErrorCode.INVALID_RESPONSE),
        (completion(finish="length"), ErrorCode.TRUNCATED),
        (completion(None, refusal=SECRET), ErrorCode.REFUSAL),
        (completion(finish="content_filter"), ErrorCode.REFUSAL),
        (completion(finish="tool_calls"), ErrorCode.INVALID_RESPONSE),
        ({"choices": []}, ErrorCode.INVALID_RESPONSE),
        ({"choices": "unexpected"}, ErrorCode.INVALID_RESPONSE),
    ],
)
async def test_bad_model_results_fail_without_hidden_repair(payload, code):
    allowance = budget()
    async with NebiusProvider(
        settings(max_retries=2),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload)),
    ) as provider:
        with pytest.raises(ProviderError) as caught:
            await generate(provider, allowance)
    assert caught.value.code == code
    assert allowance.used["model"] == 1
    assert allowance.attempts[0].outcome == code.value
    assert SECRET not in "".join(traceback.format_exception(caught.value))


async def test_search_fields_and_empty_results_are_success():
    def handle(request):
        body = json.loads(request.content)
        assert str(request.url) == "https://api.tavily.com/search"
        assert body["search_depth"] == "advanced"
        assert not body["include_answer"] and not body["include_raw_content"]
        assert not body["auto_parameters"]
        return httpx.Response(200, json={"results": [], "usage": {"credits": 2}})

    async with TavilyProvider(settings(), transport=httpx.MockTransport(handle)) as provider:
        result = await provider.search("A precise query", budget=budget())
    assert result.results == () and result.usage.credits == 2
    assert result.retrieved_at.tzinfo is UTC


async def test_search_preserves_metadata_without_inventing_dates():
    hits = [{"url": URL_A, "title": "Record", "content": "A snippet", "score": 0.9}]
    async with TavilyProvider(
        settings(),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"results": hits})),
    ) as provider:
        result = await provider.search("Record", budget=budget())
    assert result.results[0].url == URL_A
    assert result.results[0].published_date is None
    assert result.results[0].content == "A snippet"
    assert result.usage is None


async def test_extract_preserves_content_order_partial_and_missing_results():
    url_c = "https://example.org/c"
    original = "# Heading\n\nReported **2023**, not 2024.\n"

    def handle(request):
        body = json.loads(request.content)
        assert body["urls"] == [URL_A, URL_B, url_c]
        assert "query" not in body and body["format"] == "markdown"
        return httpx.Response(
            200,
            json={
                "results": [{"url": URL_B, "raw_content": original}],
                "failed_results": [{"url": URL_A, "error": SECRET}],
            },
        )

    allowance = budget()
    async with TavilyProvider(settings(), transport=httpx.MockTransport(handle)) as provider:
        result = await provider.extract([URL_A, URL_B, url_c], budget=allowance)
    assert [page.url for page in result.pages] == [URL_A, URL_B, url_c]
    assert result.pages[0].error == "extraction_failed"
    assert result.pages[1].content == original and result.pages[1].error is None
    assert result.pages[2].error == "missing_result"
    assert allowance.used["extract"] == 3
    assert SECRET not in repr(result)


@pytest.mark.parametrize(
    "results,failures",
    [
        ([{"url": URL_B, "raw_content": "unrequested"}], []),
        ([{"url": URL_A, "raw_content": "a"}] * 2, []),
        ([{"url": URL_A, "raw_content": "a"}], [{"url": URL_A}]),
    ],
)
async def test_extract_rejects_untraceable_or_ambiguous_pages(results, failures):
    async with TavilyProvider(
        settings(),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"results": results, "failed_results": failures}
            )
        ),
    ) as provider:
        with pytest.raises(ProviderError, match="invalid_response"):
            await provider.extract([URL_A], budget=budget())


async def test_empty_extraction_is_a_page_failure():
    async with TavilyProvider(
        settings(),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "results": [{"url": URL_A, "raw_content": "  "}],
                    "failed_results": [],
                },
            )
        ),
    ) as provider:
        result = await provider.extract([URL_A], budget=budget())
    assert result.pages[0].content is None and result.pages[0].error == "empty_content"


@pytest.mark.parametrize(
    "status,code",
    [
        (400, ErrorCode.INVALID_REQUEST),
        (401, ErrorCode.AUTHENTICATION),
        (403, ErrorCode.AUTHENTICATION),
        (402, ErrorCode.QUOTA),
        (404, ErrorCode.INVALID_REQUEST),
        (422, ErrorCode.INVALID_REQUEST),
        (432, ErrorCode.QUOTA),
        (433, ErrorCode.QUOTA),
        (302, ErrorCode.INVALID_REQUEST),
    ],
)
async def test_permanent_failures_are_redacted_and_never_retried(status, code, caplog):
    allowance = budget()
    async with TavilyProvider(
        settings(max_retries=2),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                status, text=SECRET, headers={"location": "https://example.org/secret"}
            )
        ),
    ) as provider:
        with pytest.raises(ProviderError) as caught:
            await provider.search("query", budget=allowance)
    assert caught.value.code == code and caught.value.status_code == status
    assert allowance.used["search"] == 1
    assert SECRET not in repr(caught.value) + caplog.text + repr(allowance.attempts)


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
async def test_transient_failure_retries_and_counts_every_attempt(status, monkeypatch):
    delays = []

    async def sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("aletheia.providers.common.asyncio.sleep", sleep)
    count = 0

    def handle(request):
        nonlocal count
        count += 1
        if count < 3:
            return httpx.Response(status, headers={"Retry-After": "1"}, text=SECRET)
        return httpx.Response(200, json={"results": []})

    allowance = budget()
    async with TavilyProvider(
        settings(max_retries=2), transport=httpx.MockTransport(handle)
    ) as provider:
        await provider.search("query", budget=allowance)
    assert allowance.used["search"] == 3 and delays == [1, 1]
    assert [a.status_code for a in allowance.attempts] == [status, status, 200]


async def test_retries_stop_at_two_even_with_large_budget(monkeypatch):
    async def sleep(delay):
        pass

    monkeypatch.setattr("aletheia.providers.common.asyncio.sleep", sleep)
    allowance = budget(search_attempts=100)
    async with TavilyProvider(
        settings(max_retries=2), transport=httpx.MockTransport(lambda request: httpx.Response(503))
    ) as provider:
        with pytest.raises(ProviderError, match="unavailable"):
            await provider.search("query", budget=allowance)
    assert allowance.used["search"] == 3


async def test_retry_after_beyond_deadline_does_not_retry():
    allowance = budget()
    async with TavilyProvider(
        settings(max_retries=2),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(429, headers={"Retry-After": "3600"})
        ),
    ) as provider:
        with pytest.raises(ProviderError, match="rate_limited"):
            await provider.search("query", budget=allowance)
    assert allowance.used["search"] == 1


def test_retry_after_accepts_http_dates_and_ignores_invalid_values():
    assert retry_delay("2") == 2 and retry_delay("-1") == 0
    assert retry_delay("NaN") is None and retry_delay(SECRET) is None
    assert 25 <= retry_delay(format_datetime(datetime.now(UTC) + timedelta(seconds=30))) <= 30


async def test_extraction_retry_reserves_all_urls_before_dispatch():
    allowance = budget(extraction_attempts=3)
    async with TavilyProvider(
        settings(max_retries=2), transport=httpx.MockTransport(lambda request: httpx.Response(503))
    ) as provider:
        with pytest.raises(ProviderError, match="budget_exhausted"):
            await provider.extract([URL_A, URL_B], budget=allowance)
    assert allowance.used["extract"] == 2 and len(allowance.attempts) == 1


async def test_deadline_blocks_new_attempts_and_cancels_slow_response():
    count = 0

    async def handle(request):
        nonlocal count
        count += 1
        await asyncio.sleep(0.1)
        return httpx.Response(200, json={"results": []})

    async with TavilyProvider(settings(), transport=httpx.MockTransport(handle)) as provider:
        expired = budget(deadline=time.monotonic() - 1)
        with pytest.raises(ProviderError, match="deadline_exceeded"):
            await provider.search("query", budget=expired)
        assert count == 0 and expired.used["search"] == 0
        short = budget(deadline=time.monotonic() + 0.02)
        with pytest.raises(ProviderError, match="deadline_exceeded"):
            await provider.search("query", budget=short)
        assert count == 1 and short.attempts[0].outcome == "deadline_exceeded"


async def test_concurrent_calls_cannot_overspend_shared_budget():
    allowance = budget(search_attempts=1)

    async def handle(request):
        await asyncio.sleep(0.01)
        return httpx.Response(200, json={"results": []})

    async with TavilyProvider(settings(), transport=httpx.MockTransport(handle)) as provider:
        results = await asyncio.gather(
            *[provider.search("query", budget=allowance) for _ in range(2)], return_exceptions=True
        )
    assert sum(isinstance(r, ProviderError) for r in results) == 1
    assert allowance.used["search"] == 1 and len(allowance.attempts) == 1


@pytest.mark.parametrize(
    "exception,code",
    [
        (httpx.ReadTimeout, ErrorCode.TIMEOUT),
        (httpx.ConnectError, ErrorCode.NETWORK),
    ],
)
async def test_transport_errors_are_safe(exception, code):
    def handle(request):
        raise exception(SECRET, request=request)

    async with TavilyProvider(settings(), transport=httpx.MockTransport(handle)) as provider:
        with pytest.raises(ProviderError) as caught:
            await provider.search("query", budget=budget())
    assert caught.value.code == code
    assert SECRET not in "".join(traceback.format_exception(caught.value))


async def test_cancellation_propagates_and_is_accounted():
    async def handle(request):
        raise asyncio.CancelledError

    allowance = budget()
    async with TavilyProvider(settings(), transport=httpx.MockTransport(handle)) as provider:
        with pytest.raises(asyncio.CancelledError):
            await provider.search("query", budget=allowance)
    assert allowance.used["search"] == 1 and allowance.attempts[0].outcome == "cancelled"


@pytest.mark.parametrize(
    "body,code",
    [
        (b"x" * 1025, "response_too_large"),
        (b"not json", "invalid_response"),
        (b"[]", "invalid_response"),
        (b"{}", "invalid_response"),
    ],
)
async def test_response_size_and_schema_limits(body, code):
    async with TavilyProvider(
        settings(max_response_bytes=1024),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=body)),
    ) as provider:
        with pytest.raises(ProviderError, match=code):
            await provider.search("query", budget=budget())


async def test_invalid_inputs_do_not_consume_budget():
    def handle(request):
        pytest.fail("Invalid input must not reach transport")

    allowance = budget()
    async with TavilyProvider(settings(), transport=httpx.MockTransport(handle)) as provider:
        for query in ("", " ", "x" * 401):
            with pytest.raises(ProviderError, match="invalid_request"):
                await provider.search(query, budget=allowance)
        for urls in (
            [],
            [URL_A, URL_A],
            ["file:///tmp/secret"],
            ["https://user:secret@example.org"],
        ):
            with pytest.raises(ProviderError, match="invalid_request"):
                await provider.extract(urls, budget=allowance)
    async with NebiusProvider(
        settings(max_request_bytes=1024), transport=httpx.MockTransport(handle)
    ) as provider:
        with pytest.raises(ProviderError, match="invalid_request"):
            await provider.generate(
                instructions="x" * 2000, input_text="x", response_type=Answer, budget=allowance
            )
    assert not allowance.attempts and sum(allowance.used.values()) == 0


def test_provider_config_redaction_and_missing_credentials():
    assert SECRET not in repr(settings()) + settings().model_dump_json()
    assert isinstance(settings().nebius_api_key, SecretStr)
    with pytest.raises(ProviderError, match="configuration"):
        NebiusProvider(ProviderSettings())
    with pytest.raises(ProviderError, match="configuration"):
        TavilyProvider(ProviderSettings())


def test_environment_configuration_does_not_load_dotenv_by_default(monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", SECRET)
    monkeypatch.setenv("NEBIUS_MODEL", "fixture/model")
    monkeypatch.setenv("ALETHEIA_PROVIDER_MAX_RETRIES", "1")
    monkeypatch.setattr(
        "aletheia.providers.settings.load_dotenv", lambda **kw: pytest.fail("No implicit dotenv")
    )
    loaded = ProviderSettings.from_environment()
    assert loaded.max_retries == 1 and loaded.nebius_model == "fixture/model"
    monkeypatch.setenv("ALETHEIA_PROVIDER_MAX_RETRIES", SECRET)
    with pytest.raises(ConfigurationError) as caught:
        ProviderSettings.from_environment()
    assert SECRET not in str(caught.value)


def test_explicit_runtime_dotenv_preserves_environment(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr("aletheia.providers.settings.load_dotenv", lambda **kw: calls.append(kw))
    path = tmp_path / "runtime-config"
    ProviderSettings.from_environment(dotenv_path=path)
    assert calls == [{"dotenv_path": path, "override": False}]
