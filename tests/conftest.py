import pytest
from httpx import ASGITransport, AsyncClient

from aletheia.api import create_app
from aletheia.config import Settings


@pytest.fixture(autouse=True)
def forbid_dotenv(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Tests must not load real dotenv files.")

    monkeypatch.setattr("aletheia.config.load_dotenv", forbidden)
    monkeypatch.setattr("aletheia.providers.settings.load_dotenv", forbidden)


@pytest.fixture(autouse=True)
def isolate_provider_environment(monkeypatch):
    # Never let real shell credentials/settings affect offline test outcomes.
    for name in (
        "NEBIUS_API_KEY",
        "TAVILY_API_KEY",
        "NEBIUS_MODEL",
        "ALETHEIA_NEBIUS_RESPONSE_FORMAT",
        "ALETHEIA_PROVIDER_TIMEOUT_SECONDS",
        "ALETHEIA_PROVIDER_MAX_RETRIES",
        "ALETHEIA_PROVIDER_MAX_REQUEST_BYTES",
        "ALETHEIA_PROVIDER_MAX_RESPONSE_BYTES",
        "ALETHEIA_MODEL_MAX_OUTPUT_TOKENS",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def settings(tmp_path):
    return Settings(database_path=tmp_path / "investigations.sqlite3")


@pytest.fixture
async def app(settings):
    application = create_app(settings)
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as session:
        yield session
