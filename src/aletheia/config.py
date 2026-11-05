"""Runtime settings. Provider credentials are not needed by the foundation."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigurationError(Exception):
    """A safe configuration error, containing no supplied values."""


@dataclass(frozen=True)
class Settings:
    database_path: Path = Path("data/aletheia.sqlite3")
    queue_limit: int = 100
    # All 24,000 allowed characters may use 12-byte escaped surrogate pairs in JSON.
    max_body_bytes: int = 327_680

    def __post_init__(self) -> None:
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
        try:
            return cls(
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
