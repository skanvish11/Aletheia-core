"""The live entry point is opt-in and its reporting works offline too."""

import importlib.util
import json
from pathlib import Path

import httpx
import pytest

from aletheia.config import ProviderSettings
from aletheia.providers.nebius import NebiusProvider
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


@pytest.mark.parametrize("profile", ["smoke", "representative"])
async def test_smoke_report_measures_actual_operations_without_content(monkeypatch, profile):
    def handle(request):
        body = json.loads(request.content)
        if request.url.path.endswith("chat/completions"):
            value = {"label": "alpha", "year": 2023}
            if "12 items" in body["messages"][1]["content"]:
                value = {"items": [{"label": f"item-{i}", "year": 2023} for i in range(1, 13)]}
            if "40 items" in body["messages"][1]["content"]:
                value = {"items": [{"label": f"item-{i}", "year": 2023} for i in range(1, 41)]}
            if "publication year from the catalog" in body["messages"][1]["content"]:
                value = {"label": "record-317", "year": 1917}
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

    async def retry_timing():
        return {"source": "fixture"}

    monkeypatch.setattr(smoke, "measure_retry_timing", retry_timing)
    report = await smoke.measure(settings, samples=2, deadline_seconds=30, profile=profile)
    assert report["passed"] and len(report["checks"]) == 6
    assert report["attempt_units"] == {"model": 4, "search": 1, "extract": 1}
    label = "nebius_large_output" if profile == "representative" else "nebius_long"
    assert report["latency_seconds"][label]["count"] == 2
    if profile == "representative":
        assert report["checks"][0]["input_characters"] > 70_000
        assert report["checks"][0]["output_characters"] > 0
        assert report["offline_retry_timing"]["source"] == "fixture"
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


async def test_retry_measurement_is_offline_and_includes_backoff():
    report = await smoke.measure_retry_timing()
    assert report["elapsed_seconds"] >= 1.05
    assert report["scheduled_backoff_seconds"] == 0.75
    assert [a["status_code"] for a in report["attempts"]] == [503, 503, 200]
    assert sum(a["units"] for a in report["attempts"]) == 3
    assert "offline simulation" in report["source"]
