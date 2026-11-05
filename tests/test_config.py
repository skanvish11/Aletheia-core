from pathlib import Path

import pytest

from aletheia.api import create_app
from aletheia.config import ConfigurationError, Settings
from aletheia.main import run
from aletheia.storage import StorageError


@pytest.mark.parametrize(
    "kwargs",
    [
        {"queue_limit": 0},
        {"queue_limit": True},
        {"queue_limit": 10001},
        {"max_body_bytes": 100},
        {"max_body_bytes": 1048577},
        {"database_path": Path(":memory:")},
        {"database_path": Path("")},
        {"database_path": Path("synthetic-secret\x00.db")},
    ],
)
def test_invalid_settings(kwargs):
    with pytest.raises(ConfigurationError):
        Settings(**kwargs)


def test_missing_provider_keys_do_not_prevent_creation(settings, monkeypatch):
    for name in ("NEBIUS_API_KEY", "TAVILY_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert create_app(settings) is not None


def test_environment_and_dotenv_override_policy(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr("aletheia.config.load_dotenv", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setenv("ALETHEIA_DATABASE_PATH", str(tmp_path / "configured.db"))
    monkeypatch.setenv("ALETHEIA_QUEUE_LIMIT", "5")
    monkeypatch.setenv("ALETHEIA_MAX_BODY_BYTES", "4096")
    settings = Settings.from_environment()
    assert settings.database_path == tmp_path / "configured.db"
    assert settings.queue_limit == 5
    assert settings.max_body_bytes == 4096
    assert calls == [{"dotenv_path": Path(".env"), "override": False}]


def test_startup_error_does_not_disclose_invalid_setting(monkeypatch, capsys):
    monkeypatch.setattr("aletheia.config.load_dotenv", lambda **kwargs: None)
    monkeypatch.setenv("ALETHEIA_QUEUE_LIMIT", "synthetic-secret")
    with pytest.raises(SystemExit) as exc:
        run()
    assert exc.value.code == 2
    output = capsys.readouterr()
    assert "configuration" in output.err
    assert "synthetic-secret" not in output.err + output.out


async def test_inaccessible_database_startup_is_redacted(tmp_path):
    blocked = tmp_path / "synthetic-secret-parent"
    blocked.write_text("An ordinary file blocks directory creation")
    app = create_app(Settings(database_path=blocked / "db.sqlite3"))
    with pytest.raises(StorageError) as exc:
        async with app.router.lifespan_context(app):
            pytest.fail("Application must not start without storage")
    assert "synthetic-secret" not in str(exc.value)
