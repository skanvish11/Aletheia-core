"""Tavily search and full-page extraction with explicit per-URL outcomes."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Literal
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from aletheia.providers.common import CallBudget, ErrorCode, ProviderError, ProviderHTTP
from aletheia.providers.settings import ProviderSettings


def valid_url(value: str) -> str:
    parts = urlsplit(value)
    if (
        parts.scheme not in ("http", "https")
        or not parts.hostname
        or parts.username
        or parts.password
        or any(c.isspace() or ord(c) < 32 for c in value)
    ):
        raise ValueError("Expected an HTTP(S) URL without credentials.")
    return value


class WireModel(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, allow_inf_nan=False)


class CreditUsage(WireModel):
    credits: Annotated[float, Field(ge=0)]


class SearchHit(WireModel):
    url: Annotated[str, Field(min_length=1, max_length=8192)]
    title: str
    content: str
    score: Annotated[float, Field(ge=0, le=1)]
    published_date: str | None = None

    _url = field_validator("url")(valid_url)


class SearchResponse(WireModel):
    results: Annotated[list[SearchHit], Field(max_length=20)]
    usage: CreditUsage | None = None


class ExtractHit(WireModel):
    url: Annotated[str, Field(min_length=1, max_length=8192)]
    raw_content: str

    _url = field_validator("url")(valid_url)


class ExtractFailure(WireModel):
    url: Annotated[str, Field(min_length=1, max_length=8192)]
    # Intentionally do not retain provider-supplied error text.

    _url = field_validator("url")(valid_url)


class ExtractResponse(WireModel):
    results: Annotated[list[ExtractHit], Field(max_length=20)]
    failed_results: Annotated[list[ExtractFailure], Field(max_length=20)]
    usage: CreditUsage | None = None


@dataclass(frozen=True)
class SearchResult:
    results: tuple[SearchHit, ...]
    retrieved_at: datetime
    usage: CreditUsage | None


@dataclass(frozen=True)
class PageOutcome:
    url: str
    content: str | None
    error: Literal["extraction_failed", "empty_content", "missing_result"] | None


@dataclass(frozen=True)
class ExtractionResult:
    pages: tuple[PageOutcome, ...]
    retrieved_at: datetime
    usage: CreditUsage | None


class TavilyProvider(ProviderHTTP):
    def __init__(
        self, settings: ProviderSettings, *, transport: httpx.AsyncBaseTransport | None = None
    ):
        super().__init__("tavily", settings, transport=transport)

    async def search(
        self,
        query: str,
        *,
        budget: CallBudget,
        max_results: int = 5,
        depth: Literal["basic", "advanced"] = "advanced",
    ) -> SearchResult:
        if (
            not isinstance(query, str)
            or not query.strip()
            or len(query) > 400
            or type(max_results) is not int
            or not 1 <= max_results <= 20
            or depth not in ("basic", "advanced")
        ):
            raise ProviderError("tavily", ErrorCode.INVALID_REQUEST)
        payload = {
            "query": query,
            "max_results": max_results,
            "search_depth": depth,
            "topic": "general",
            "include_answer": False,
            "include_raw_content": False,
            "include_images": False,
            "auto_parameters": False,
            "include_usage": True,
        }

        def parse(data: dict) -> SearchResult:
            response = SearchResponse.model_validate(data)
            if len(response.results) > max_results:
                raise ProviderError("tavily", ErrorCode.INVALID_RESPONSE)
            return SearchResult(tuple(response.results), datetime.now(UTC), response.usage)

        return await self.post("search", payload, budget=budget, operation="search", parse=parse)

    async def extract(
        self,
        urls: list[str],
        *,
        budget: CallBudget,
        depth: Literal["basic", "advanced"] = "basic",
    ) -> ExtractionResult:
        try:
            if (
                not isinstance(urls, list)
                or not 1 <= len(urls) <= 20
                or depth not in ("basic", "advanced")
            ):
                raise ValueError
            if any(not isinstance(url, str) or len(url) > 8192 for url in urls):
                raise ValueError
            requested = tuple(valid_url(url) for url in urls)
            if len(set(requested)) != len(requested):
                raise ValueError
        except (ValueError, TypeError):
            raise ProviderError("tavily", ErrorCode.INVALID_REQUEST) from None
        payload = {
            "urls": requested,
            "extract_depth": depth,
            "format": "markdown",
            "include_images": False,
            "include_usage": True,
            "timeout": min(60.0, self.settings.timeout_seconds),
        }

        def parse(data: dict) -> ExtractionResult:
            response = ExtractResponse.model_validate(data)
            pages = {}
            for item in response.results:
                if item.url not in requested or item.url in pages:
                    raise ProviderError("tavily", ErrorCode.INVALID_RESPONSE)
                pages[item.url] = PageOutcome(
                    item.url,
                    item.raw_content if item.raw_content.strip() else None,
                    None if item.raw_content.strip() else "empty_content",
                )
            for item in response.failed_results:
                if item.url not in requested or item.url in pages:
                    raise ProviderError("tavily", ErrorCode.INVALID_RESPONSE)
                pages[item.url] = PageOutcome(item.url, None, "extraction_failed")
            return ExtractionResult(
                tuple(
                    pages.get(url, PageOutcome(url, None, "missing_result")) for url in requested
                ),
                datetime.now(UTC),
                response.usage,
            )

        return await self.post(
            "extract",
            payload,
            budget=budget,
            operation="extract",
            units=len(requested),
            parse=parse,
        )
