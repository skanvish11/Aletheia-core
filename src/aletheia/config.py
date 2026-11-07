"""Runtime settings. Provider credentials are not needed by the foundation."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator


class ConfigurationError(Exception):
    """A safe configuration error, containing no supplied values."""


@dataclass(frozen=True)
class Settings:
    database_path: Path = Path("data/aletheia.sqlite3")
    queue_limit: int = 100
    research_enabled: bool = False
    # All 24,000 allowed characters may use 12-byte escaped surrogate pairs in JSON.
    max_body_bytes: int = 327_680

    def __post_init__(self) -> None:
        if type(self.research_enabled) is not bool:
            raise ConfigurationError("ALETHEIA_RESEARCH_ENABLED must be true or false.")
        if (
            not isinstance(self.database_path, Path)
            or str(self.database_path) in (".", ":memory:")
            or "\x00" in str(self.database_path)
        ):
            raise ConfigurationError("ALETHEIA_DATABASE_PATH must name a persistent database file.")
        if type(self.queue_limit) is not int or not 1 <= self.queue_limit <= 10_000:
            raise ConfigurationError("ALETHEIA_QUEUE_LIMIT must be an integer from 1 to 10000.")
        if type(self.max_body_bytes) is not int or not 1_024 <= self.max_body_bytes <= 1_048_576:
            raise ConfigurationError("ALETHEIA_MAX_BODY_BYTES must be from 1024 to 1048576.")

    @classmethod
    def from_environment(cls) -> "Settings":
        # Only application runtime loads dotenv. Explicit Settings in tests bypass it.
        load_dotenv(dotenv_path=Path(".env"), override=False)
        enabled = os.environ.get("ALETHEIA_RESEARCH_ENABLED", "false").lower()
        if enabled not in {"true", "false"}:
            raise ConfigurationError("ALETHEIA_RESEARCH_ENABLED must be true or false.")
        try:
            return cls(
                research_enabled=enabled == "true",
                database_path=Path(
                    os.environ.get("ALETHEIA_DATABASE_PATH", "data/aletheia.sqlite3")
                ),
                queue_limit=int(os.environ.get("ALETHEIA_QUEUE_LIMIT", "100")),
                max_body_bytes=int(os.environ.get("ALETHEIA_MAX_BODY_BYTES", "327680")),
            )
        except (ValueError, TypeError):
            raise ConfigurationError(
                "Invalid Aletheia configuration; check documented settings."
            ) from None


PROVIDER_ENV = {
    "nebius_api_key": "NEBIUS_API_KEY",
    "tavily_api_key": "TAVILY_API_KEY",
    "nebius_model": "NEBIUS_MODEL",
    "nebius_response_format": "ALETHEIA_NEBIUS_RESPONSE_FORMAT",
    "nebius_thinking": "ALETHEIA_NEBIUS_THINKING",
    "timeout_seconds": "ALETHEIA_PROVIDER_TIMEOUT_SECONDS",
    "max_retries": "ALETHEIA_PROVIDER_MAX_RETRIES",
    "max_request_bytes": "ALETHEIA_PROVIDER_MAX_REQUEST_BYTES",
    "max_response_bytes": "ALETHEIA_PROVIDER_MAX_RESPONSE_BYTES",
    "max_extracted_chars": "ALETHEIA_MAX_EXTRACTED_CHARS",
    "max_output_tokens": "ALETHEIA_MODEL_MAX_OUTPUT_TOKENS",
}

# Add a model only after verifying its chat-template control contract.
NEBIUS_THINKING_MODELS = frozenset({"nvidia/Nemotron-3_5-Lightning"})


class ProviderSettings(BaseModel):
    """One immutable model/format/output-cap selection; never a cross-model fallback."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    nebius_api_key: SecretStr | None = Field(default=None, repr=False)
    tavily_api_key: SecretStr | None = Field(default=None, repr=False)
    nebius_model: str | None = Field(default=None, min_length=1, max_length=200)
    nebius_response_format: Literal["json_schema", "json_object"] = "json_schema"
    nebius_thinking: Literal["default", "enabled", "disabled"] = "default"
    timeout_seconds: float = Field(default=45.0, ge=1, le=120, allow_inf_nan=False)
    max_retries: int = Field(default=2, ge=0, le=2, strict=True)
    max_request_bytes: int = Field(default=262_144, ge=1024, le=1_048_576, strict=True)
    max_response_bytes: int = Field(default=2_097_152, ge=1024, le=10_485_760, strict=True)
    max_extracted_chars: int = Field(default=100_000, ge=1024, le=1_000_000, strict=True)
    max_output_tokens: int = Field(default=4096, ge=64, le=16_384, strict=True)

    def validate_model_controls(self):
        if self.nebius_thinking != "default" and self.nebius_model not in NEBIUS_THINKING_MODELS:
            raise ConfigurationError(
                "ALETHEIA_NEBIUS_THINKING requires a model with verified thinking controls; "
                "use default for other models."
            )

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
        values = {
            field: os.environ[name] for field, name in PROVIDER_ENV.items() if name in os.environ
        }
        try:
            for field in (
                "max_retries",
                "max_request_bytes",
                "max_response_bytes",
                "max_output_tokens",
                "max_extracted_chars",
            ):
                if field in values:
                    values[field] = int(values[field])
            return cls(**values)
        except (ValueError, TypeError, ValidationError):
            raise ConfigurationError(
                "Invalid provider settings; check documented settings."
            ) from None
