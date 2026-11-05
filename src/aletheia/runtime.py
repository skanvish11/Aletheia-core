"""Explicit opt-in provider lifecycle; runtime alone reads environment settings."""

from contextlib import asynccontextmanager

from aletheia.config import ConfigurationError, ProviderSettings
from aletheia.providers.errors import ProviderError
from aletheia.providers.nebius import NebiusProvider
from aletheia.providers.tavily import TavilyProvider


@asynccontextmanager
async def research_providers():
    settings = ProviderSettings.from_environment()
    try:
        async with NebiusProvider(settings) as model, TavilyProvider(settings) as search:
            yield model, search, settings.nebius_model
    except ProviderError:
        raise ConfigurationError(
            "Research providers require valid documented configuration."
        ) from None
