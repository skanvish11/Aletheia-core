"""Nebius structured inference; task-specific meaning stays with the caller."""

import json
from dataclasses import dataclass
from functools import partial
from typing import Annotated

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

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
    reasoning_tokens: int | None = None
    output_chars: int | None = None


def parse_completion[T: BaseModel](data: dict, *, response_type: type[T]) -> ModelResult[T]:
    try:
        completion = Completion.model_validate(data)
    except ValidationError:
        error = ProviderError("nebius", ErrorCode.INVALID_RESPONSE)
        error.validation_code = "response_envelope"
        raise error from None
    choice = completion.choices[0]
    details = (data.get("usage") or {}).get("completion_tokens_details")
    reasoning = details.get("reasoning_tokens") if isinstance(details, dict) else None
    if (
        type(reasoning) is not int
        or completion.usage is None
        or not 0 <= reasoning <= completion.usage.completion_tokens
    ):
        reasoning = None
    output_chars = len(choice.message.content) if choice.message.content is not None else 0

    def failure(code, validation="unknown"):
        error = ProviderError("nebius", code)
        error.validation_code = validation
        error.reasoning_tokens, error.output_chars = reasoning, output_chars
        if choice.finish_reason in {"length", "content_filter", "stop"}:
            error.finish_reason = choice.finish_reason
        error.token_usage = completion.usage.model_dump() if completion.usage else None
        return error

    if choice.message.refusal or choice.finish_reason == "content_filter":
        raise failure(ErrorCode.REFUSAL)
    if choice.finish_reason == "length":
        raise failure(ErrorCode.TRUNCATED)
    if (
        choice.finish_reason != "stop"
        or choice.message.role != "assistant"
        or not choice.message.content
    ):
        raise failure(ErrorCode.INVALID_RESPONSE, "response_shape")
    # Python validation is required even with provider-side schema constraints.
    # JSON parsing first prevents Pydantic's permissive JSON type conversions.
    try:
        decoded = parse_json(choice.message.content)
    except (ValueError, RecursionError):
        raise failure(ErrorCode.INVALID_RESPONSE, "response_json") from None
    try:
        value = response_type.model_validate(decoded, strict=True)
    except ValidationError as exc:
        error = failure(ErrorCode.INVALID_RESPONSE, "response_schema")
        # Never export error messages, input values, context, or untrusted extra keys.
        errors = exc.errors(include_input=False, include_context=False, include_url=False)
        fields = {
            e["loc"][0] for e in errors if e["loc"] and e["loc"][0] in response_type.model_fields
        }
        allowed_types = {
            "missing",
            "extra_forbidden",
            "string_type",
            "string_too_long",
            "string_too_short",
            "int_type",
            "bool_type",
            "literal_error",
            "too_long",
            "too_short",
            "list_type",
            "model_type",
            "greater_than_equal",
            "less_than_equal",
            "value_error",
        }
        types = {e["type"] if e["type"] in allowed_types else "other" for e in errors}
        error.schema_fields = ",".join(sorted(fields)[:8]) or "unknown"
        error.schema_error_types = ",".join(sorted(types)[:8]) or "unknown"
        raise error from None
    return ModelResult(value, completion.usage, reasoning, output_chars)


class NebiusProvider(ProviderHTTP):
    def __init__(
        self, settings: ProviderSettings, *, transport: httpx.AsyncBaseTransport | None = None
    ):
        if settings.nebius_model is None:
            raise ProviderError("nebius", ErrorCode.CONFIGURATION)
        settings.validate_model_controls()
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
        if self.settings.nebius_thinking != "default":
            payload["chat_template_kwargs"] = {
                "enable_thinking": self.settings.nebius_thinking == "enabled"
            }

        return await self.post(
            "chat/completions",
            payload,
            budget=budget,
            operation="model",
            parse=partial(parse_completion, response_type=response_type),
        )
