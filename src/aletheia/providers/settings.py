"""Provider-only settings, loaded separately from the offline API foundation."""

import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator

from aletheia.config import ConfigurationError


class ProviderSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    nebius_api_key: SecretStr | None = Field(default=None, repr=False)
    tavily_api_key: SecretStr | None = Field(default=None, repr=False)
    nebius_model: str | None = Field(default=None, min_length=1, max_length=200)
    nebius_response_format: Literal["json_schema", "json_object"] = "json_schema"
    timeout_seconds: float = Field(default=45.0, ge=1, le=120, allow_inf_nan=False)
    max_retries: int = Field(default=2, ge=0, le=2, strict=True)
    max_request_bytes: int = Field(default=262_144, ge=1024, le=1_048_576, strict=True)
    max_response_bytes: int = Field(default=2_097_152, ge=1024, le=10_485_760, strict=True)
    max_output_tokens: int = Field(default=2048, ge=64, le=16_384, strict=True)

    @field_validator("nebius_api_key", "tavily_api_key")
    @classmethod
    def valid_key(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None:
            key = value.get_secret_value()
            if not key or any(ord(c) < 33 or ord(c) > 126 for c in key):
                raise ValueError("Provider key must be a nonempty ASCII token.")
        return value

    @field_validator("nebius_model")
    @classmethod
    def valid_model(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or any(c.isspace() for c in value)):
            raise ValueError("Model must be a nonempty identifier without whitespace.")
        return value

    @classmethod
    def from_environment(cls, *, dotenv_path: Path | None = None) -> "ProviderSettings":
        # An explicit runtime path only; never search parents or print file contents.
        if dotenv_path is not None:
            load_dotenv(dotenv_path=dotenv_path, override=False)
        names = {
            "nebius_api_key": "NEBIUS_API_KEY",
            "tavily_api_key": "TAVILY_API_KEY",
            "nebius_model": "NEBIUS_MODEL",
            "nebius_response_format": "ALETHEIA_NEBIUS_RESPONSE_FORMAT",
            "timeout_seconds": "ALETHEIA_PROVIDER_TIMEOUT_SECONDS",
            "max_retries": "ALETHEIA_PROVIDER_MAX_RETRIES",
            "max_request_bytes": "ALETHEIA_PROVIDER_MAX_REQUEST_BYTES",
            "max_response_bytes": "ALETHEIA_PROVIDER_MAX_RESPONSE_BYTES",
            "max_output_tokens": "ALETHEIA_MODEL_MAX_OUTPUT_TOKENS",
        }
        values = {field: os.environ[name] for field, name in names.items() if name in os.environ}
        try:
            for field in (
                "max_retries",
                "max_request_bytes",
                "max_response_bytes",
                "max_output_tokens",
            ):
                if field in values:
                    values[field] = int(values[field])
            return cls(**values)
        except (ValueError, TypeError, ValidationError):
            raise ConfigurationError(
                "Invalid provider settings; check documented settings."
            ) from None
