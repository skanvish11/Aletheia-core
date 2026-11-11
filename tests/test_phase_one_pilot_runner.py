"""Pilot identity and accounting checks; fake executors never call providers."""

import importlib.util
import sys
from pathlib import Path

import pytest

from aletheia.config import ProviderSettings
from aletheia.evaluation import write_json

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(
        "phase_one_pilot_runner", SCRIPTS / "rerun_phase_one_pilot.py"
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def test_same_ordered_pilot_and_hash(runner):
    cases, baseline = runner.load_pilot()
    assert [c.id for c in cases] == [f"b{i:04d}" for i in range(1, 31)]
    assert runner.dataset_hash(cases) == baseline["dataset_sha256"]
    for case in cases:
        assert set(case.request()) <= {"claim", "context"}


def test_unsupported_is_not_factual_completion_or_label_agreement(runner):
    cases, _ = runner.load_pilot()
    row = runner.result_row(
        cases[0],
        {
            "investigation": {
                "status": "completed",
                "result": None,
                "method_limitation": {"outcome": "unsupported_method"},
                "claim_analysis": {"required_method": "causal"},
            }
        },
    )
    result = runner.summary([row], 30)
    assert result["execution_statuses"] == {"completed": 1}
    assert result["factual_completed"] == 0 and result["unsupported_method"] == 1
    assert result["historical_label_matches"] == 0
    assert result["historical_label_denominator"] == 30 and result["not_run"] == 29


@pytest.mark.parametrize("stop", [True, False])
async def test_checkpoint_cohorts_and_stop_policy(runner, tmp_path, stop):
    cases, baseline = runner.load_pilot()
    called = []

    async def executor(args, selected, *, settings):
        case = selected[0]
        called.append(case.id)
        args.output.mkdir()
        write_json(args.output / (case.id + ".json"), {"investigation": {"status": "failed"}})
        write_json(
            args.output / "manifest.json",
            {
                "stopped_early": "configuration_failure" if stop else None,
                "restart_checks": [],
                "restart_zero_provider_calls": True,
            },
        )

    output = tmp_path / "pilot"
    await runner.execute(output, cases[:6], baseline, ProviderSettings(), executor=executor)
    result = runner.read_json(output / "summary.json")
    assert len(called) == (3 if stop else 6)
    assert result["recorded"] == len(called)
    assert result["not_run"] == 6 - len(called)
    assert result["execution_statuses"] == {"failed": len(called)}
    assert runner.read_json(output / "cases.json") == [c.model_dump() for c in cases[:6]]
    with pytest.raises(FileExistsError):
        await runner.execute(output, cases, baseline, ProviderSettings(), executor=executor)
