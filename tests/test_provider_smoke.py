"""The live entry point is opt-in and its reporting works offline too."""

import importlib.util
import json
from pathlib import Path

import httpx
import pytest

from aletheia.providers.nebius import NebiusProvider
from aletheia.providers.settings import ProviderSettings
from aletheia.providers.tavily import TavilyProvider

spec = importlib.util.spec_from_file_location(
    "provider_smoke", Path(__file__).parents[1] / "scripts" / "smoke_providers.py"
)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


def test_live_flag_is_required_before_settings_or_network(monkeypatch, capsys):
    monkeypatch.setattr(
        ProviderSettings, "from_environment", lambda **kw: pytest.fail("Not opted in")
    )
    assert smoke.main([]) == 2
    assert "No calls made" in capsys.readouterr().out


def test_missing_keys_stop_before_network(capsys):
    assert smoke.main(["--live"]) == 2
    output = capsys.readouterr().out
    assert "NEBIUS_API_KEY" in output and "TAVILY_API_KEY" in output


async def test_smoke_report_measures_actual_operations_without_content(monkeypatch):
    def handle(request):
        body = json.loads(request.content)
        if request.url.path.endswith("chat/completions"):
            value = {"label": "alpha", "year": 2023}
            if "12 items" in body["messages"][1]["content"]:
                value = {"items": [{"label": f"item-{i}", "year": 2023} for i in range(1, 13)]}
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {"role": "assistant", "content": json.dumps(value)},
                            "finish_reason": "stop",
                        }
                    ]
                },
            )
        if request.url.path.endswith("search"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "url": "https://python.org",
                            "title": "Python",
                            "content": "snippet",
                            "score": 0.9,
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "results": [{"url": "https://python.org", "raw_content": "private-response-body"}],
                "failed_results": [],
            },
        )

    transport = httpx.MockTransport(handle)
    monkeypatch.setattr(smoke, "NebiusProvider", lambda s: NebiusProvider(s, transport=transport))
    monkeypatch.setattr(smoke, "TavilyProvider", lambda s: TavilyProvider(s, transport=transport))
    settings = ProviderSettings(
        nebius_api_key="synthetic-secret",
        tavily_api_key="synthetic-secret",
        nebius_model="fixture/model",
    )
    report = await smoke.measure(settings, samples=2, deadline_seconds=30)
    assert report["passed"] and len(report["checks"]) == 6
    assert report["attempt_units"] == {"model": 4, "search": 1, "extract": 1}
    assert report["latency_seconds"]["nebius_long"]["count"] == 2
    serialized = json.dumps(report)
    assert "synthetic-secret" not in serialized and "private-response-body" not in serialized


def test_existing_output_file_is_not_overwritten_or_spent_against(monkeypatch, tmp_path):
    settings = ProviderSettings(
        nebius_api_key="synthetic", tavily_api_key="synthetic", nebius_model="fixture/model"
    )
    monkeypatch.setattr(ProviderSettings, "from_environment", lambda **kw: settings)
    monkeypatch.setattr(smoke, "measure", lambda *a, **kw: pytest.fail("No billable calls"))
    output = tmp_path / "existing.json"
    output.write_text("keep")
    assert smoke.main(["--live", "--output", str(output)]) == 2
    assert output.read_text() == "keep"
