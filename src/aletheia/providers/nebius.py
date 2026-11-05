"""Nebius structured inference; task-specific meaning stays with the caller."""

import json
from dataclasses import dataclass
from functools import partial
from typing import Annotated

import httpx
from pydantic import BaseModel, ConfigDict, Field

from aletheia.budgets import CallBudget
from aletheia.config import ProviderSettings
from aletheia.providers.common import ProviderHTTP, parse_json
from aletheia.providers.errors import ErrorCode, ProviderError

TokenCount = Annotated[int, Field(strict=True, ge=0)]


class TokenUsage(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    prompt_tokens: TokenCount
    completion_tokens: TokenCount
    total_tokens: TokenCount


class Message(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    role: str
    content: str | None
    refusal: str | None = None


class Choice(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    message: Message
    finish_reason: str


class Completion(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    choices: Annotated[list[Choice], Field(min_length=1, max_length=1)]
    usage: TokenUsage | None = None


@dataclass(frozen=True)
class ModelResult[T: BaseModel]:
    value: T
    usage: TokenUsage | None


def parse_completion[T: BaseModel](data: dict, *, response_type: type[T]) -> ModelResult[T]:
    completion = Completion.model_validate(data)
    choice = completion.choices[0]
    if choice.message.refusal or choice.finish_reason == "content_filter":
        raise ProviderError("nebius", ErrorCode.REFUSAL)
    if choice.finish_reason == "length":
        raise ProviderError("nebius", ErrorCode.TRUNCATED)
    if (
        choice.finish_reason != "stop"
        or choice.message.role != "assistant"
        or not choice.message.content
    ):
        raise ProviderError("nebius", ErrorCode.INVALID_RESPONSE)
    # Python validation is required even with provider-side schema constraints.
    # JSON parsing first prevents Pydantic's permissive JSON type conversions.
    value = response_type.model_validate(parse_json(choice.message.content), strict=True)
    return ModelResult(value, completion.usage)


class NebiusProvider(ProviderHTTP):
    def __init__(
        self, settings: ProviderSettings, *, transport: httpx.AsyncBaseTransport | None = None
    ):
        if settings.nebius_model is None:
            raise ProviderError("nebius", ErrorCode.CONFIGURATION)
        super().__init__(
            "nebius",
            settings,
            api_key=settings.nebius_api_key,
            base_url="https://api.tokenfactory.nebius.com/v1/",
            transport=transport,
        )

    async def generate[T: BaseModel](
        self,
        *,
        instructions: str,
        input_text: str,
        response_type: type[T],
        budget: CallBudget,
        max_output_tokens: int | None = None,
    ) -> ModelResult[T]:
        if (
            not isinstance(instructions, str)
            or not instructions.strip()
            or not isinstance(input_text, str)
            or not input_text.strip()
        ):
            raise ProviderError(self.provider, ErrorCode.INVALID_REQUEST)
        tokens = self.settings.max_output_tokens if max_output_tokens is None else max_output_tokens
        if type(tokens) is not int or not 1 <= tokens <= self.settings.max_output_tokens:
            raise ProviderError(self.provider, ErrorCode.INVALID_REQUEST)
        schema = response_type.model_json_schema()
        response_format = {"type": self.settings.nebius_response_format}
        if self.settings.nebius_response_format == "json_schema":
            # The deployed OpenAPI specification requires name/schema, despite older
            # guide examples passing the schema directly. Verified by the live check.
            response_format["json_schema"] = {
                "name": "aletheia_response",
                "schema": schema,
                "strict": True,
            }
        payload = {
            "model": self.settings.nebius_model,
            "messages": [
                {
                    "role": "system",
                    "content": instructions
                    + "\nReturn only JSON matching this schema:\n"
                    + json.dumps(schema),
                },
                {"role": "user", "content": input_text},
            ],
            "response_format": response_format,
            "max_tokens": tokens,
            "stream": False,
            "store": False,
        }

        return await self.post(
            "chat/completions",
            payload,
            budget=budget,
            operation="model",
            parse=partial(parse_completion, response_type=response_type),
        )
