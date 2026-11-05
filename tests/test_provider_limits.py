"""Boundary cases that protect request budgets and safe failure reporting."""

import time

import httpx
import pytest
from pydantic import ValidationError

from aletheia.budgets import CallBudget
from aletheia.config import ProviderSettings
from aletheia.providers.errors import ProviderError
from aletheia.providers.tavily import TavilyProvider


@pytest.mark.parametrize(
    "overrides",
    [
        {"max_retries": 3},
        {"max_retries": True},
        {"timeout_seconds": float("nan")},
        {"timeout_seconds": 0},
        {"max_output_tokens": 0},
        {"max_response_bytes": 0},
        {"max_extracted_chars": 0},
        {"max_extracted_chars": 1_000_001},
        {"nebius_api_key": "synthetic-secret\n"},
        {"nebius_model": " "},
        {"nebius_response_format": "text"},
    ],
)
def test_invalid_provider_settings_are_redacted(overrides):
    with pytest.raises(ValidationError) as caught:
        ProviderSettings(**overrides)
    assert "synthetic-secret" not in str(caught.value)


async def test_response_limit_closes_stream_before_reading_rest():
    seen = []

    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            for part in range(4):
                seen.append(part)
                yield b"x" * 700

        async def aclose(self):
            seen.append("closed")

    settings = ProviderSettings(tavily_api_key="synthetic", max_response_bytes=1024)
    budget = CallBudget(0, 3, 0, time.monotonic() + 10)
    async with TavilyProvider(
        settings,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=Stream())),
    ) as provider:
        with pytest.raises(ProviderError, match="response_too_large"):
            await provider.search("query", budget=budget)
    assert seen == [0, 1, "closed"]
    assert budget.used["search"] == 1


async def test_invalid_unicode_is_a_safe_input_failure():
    def handle(request):
        pytest.fail("Invalid UTF-8 input must not reach the network")

    budget = CallBudget(0, 1, 0, time.monotonic() + 10)
    async with TavilyProvider(
        ProviderSettings(tavily_api_key="synthetic"), transport=httpx.MockTransport(handle)
    ) as provider:
        with pytest.raises(ProviderError, match="invalid_request"):
            await provider.search("synthetic-secret\ud800", budget=budget)
    assert budget.used["search"] == 0


async def test_bad_compression_is_a_safe_response_failure():
    async with TavilyProvider(
        ProviderSettings(tavily_api_key="synthetic"),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, content=b"synthetic-secret", headers={"Content-Encoding": "gzip"}
            )
        ),
    ) as provider:
        with pytest.raises(ProviderError, match="invalid_response") as caught:
            await provider.search("query", budget=CallBudget(0, 1, 0, time.monotonic() + 10))
    assert "synthetic-secret" not in str(caught.value)
