"""Tavily search and full-page extraction with explicit per-URL outcomes."""

from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from typing import Annotated, Literal
from urllib.parse import urlsplit

import httpx
from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from aletheia.budgets import CallBudget
from aletheia.config import ProviderSettings
from aletheia.providers.common import ProviderHTTP
from aletheia.providers.errors import ErrorCode, ProviderError

MAX_URL_LENGTH = 8192
Depth = Literal["basic", "advanced"]
DEPTHS = ("basic", "advanced")


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


SourceURL = Annotated[
    str, Field(min_length=1, max_length=MAX_URL_LENGTH), AfterValidator(valid_url)
]


class WireModel(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, allow_inf_nan=False)


class CreditUsage(WireModel):
    credits: Annotated[float, Field(ge=0)]


class SearchHit(WireModel):
    url: SourceURL
    title: str
    content: str
    score: Annotated[float, Field(ge=0, le=1)]
    published_date: str | None = None


class SearchResponse(WireModel):
    results: Annotated[list[SearchHit], Field(max_length=20)]
    usage: CreditUsage | None = None


class ExtractHit(WireModel):
    url: SourceURL
    raw_content: str


class ExtractFailure(WireModel):
    url: SourceURL
    # Intentionally do not retain provider-supplied error text.


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
    error: str | None
    truncated: bool = False
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExtractionResult:
    pages: tuple[PageOutcome, ...]
    retrieved_at: datetime
    usage: CreditUsage | None


def parse_search(data: dict, *, max_results: int) -> SearchResult:
    response = SearchResponse.model_validate(data)
    if len(response.results) > max_results:
        raise ProviderError("tavily", ErrorCode.INVALID_RESPONSE)
    return SearchResult(tuple(response.results), datetime.now(UTC), response.usage)


def parse_extraction(data: dict, *, url: str, max_chars: int) -> ExtractionResult:
    """Validate one page independently, retaining an explicitly marked prefix if oversized."""
    response = ExtractResponse.model_validate(data)
    records = [*response.results, *response.failed_results]
    if len(records) > 1 or any(item.url != url for item in records):
        raise ProviderError("tavily", ErrorCode.INVALID_RESPONSE)
    if response.results:
        content = response.results[0].raw_content
        if not content.strip():
            page = PageOutcome(url, None, "empty_content")
        elif len(content) > max_chars:
            page = PageOutcome(
                url,
                content[:max_chars],
                None,
                truncated=True,
                limitations=("page_text_truncated",),
            )
        else:
            page = PageOutcome(url, content, None)
    else:
        page = PageOutcome(
            url, None, "extraction_failed" if response.failed_results else "missing_result"
        )
    return ExtractionResult((page,), datetime.now(UTC), response.usage)


class TavilyProvider(ProviderHTTP):
    def __init__(
        self, settings: ProviderSettings, *, transport: httpx.AsyncBaseTransport | None = None
    ):
        super().__init__(
            "tavily",
            settings,
            api_key=settings.tavily_api_key,
            base_url="https://api.tavily.com/",
            transport=transport,
        )

    async def search(
        self,
        query: str,
        *,
        budget: CallBudget,
        max_results: int = 5,
        depth: Depth = "advanced",
    ) -> SearchResult:
        if (
            not isinstance(query, str)
            or not query.strip()
            or len(query) > 400
            or type(max_results) is not int
            or not 1 <= max_results <= 20
            or depth not in DEPTHS
        ):
            raise ProviderError(self.provider, ErrorCode.INVALID_REQUEST)
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

        return await self.post(
            "search",
            payload,
            budget=budget,
            operation="search",
            parse=partial(parse_search, max_results=max_results),
        )

    async def extract(
        self,
        urls: list[str],
        *,
        budget: CallBudget,
        depth: Depth = "basic",
    ) -> ExtractionResult:
        try:
            if not isinstance(urls, list) or not 1 <= len(urls) <= 20 or depth not in DEPTHS:
                raise ValueError
            if any(not isinstance(url, str) or len(url) > MAX_URL_LENGTH for url in urls):
                raise ValueError
            requested = tuple(valid_url(url) for url in urls)
            if len(set(requested)) != len(requested):
                raise ValueError
        except (ValueError, TypeError):
            raise ProviderError(self.provider, ErrorCode.INVALID_REQUEST) from None
        payload = {
            "extract_depth": depth,
            "format": "markdown",
            "include_images": False,
            "include_usage": True,
            "timeout": min(60.0, self.settings.timeout_seconds),
        }

        pages = []
        credits = 0.0
        complete_usage = True
        stopped = None
        # One request per URL isolates response byte limits; no whole-batch retry.
        for url in requested:
            if stopped is not None:
                pages.append(PageOutcome(url, None, stopped, limitations=("page_not_attempted",)))
                continue
            try:
                result = await self.post(
                    "extract",
                    {**payload, "urls": [url]},
                    budget=budget,
                    operation="extract",
                    parse=partial(
                        parse_extraction, url=url, max_chars=self.settings.max_extracted_chars
                    ),
                )
                pages.extend(result.pages)
                if result.usage is None:
                    complete_usage = False
                else:
                    credits += result.usage.credits
            except ProviderError as exc:
                complete_usage = False
                pages.append(PageOutcome(url, None, exc.code.value, limitations=("page_omitted",)))
                if exc.code in (
                    ErrorCode.BUDGET,
                    ErrorCode.DEADLINE,
                    ErrorCode.AUTHENTICATION,
                    ErrorCode.QUOTA,
                    ErrorCode.CONFIGURATION,
                ):
                    stopped = exc.code.value
        return ExtractionResult(
            tuple(pages),
            datetime.now(UTC),
            CreditUsage(credits=credits) if complete_usage else None,
        )
