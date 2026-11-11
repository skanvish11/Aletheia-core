"""Verify the historical evidence package without calling or importing providers."""

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "handoff_inspector", ROOT / "scripts/inspect_pilot_handoff.py"
)
inspector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspector)


def test_both_runs_preserve_30_cases_and_failure_inclusive_scores():
    result = inspector.verify(inspector.DEFAULT_ROOT)
    assert result["claims"] == 30
    assert result["runs"]["original"]["statuses"] == {
        "completed": 3,
        "failed": 17,
        "partial": 5,
        "needs_clarification": 5,
    }
    assert result["runs"]["rerun"]["statuses"] == {
        "completed": 2,
        "failed": 11,
        "partial": 5,
        "needs_clarification": 12,
    }
    assert all(run["provisional_label_matches"] == 1 for run in result["runs"].values())


def test_corrupted_evidence_is_rejected_before_reporting(tmp_path):
    target = tmp_path / "handoff"
    shutil.copytree(inspector.DEFAULT_ROOT, target)
    artifact = target / "rerun/cases/b0023.json"
    data = json.loads(artifact.read_text())
    data["investigation"]["result"]["verdict"] = "almost"
    artifact.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Checksum mismatch"):
        inspector.verify(target)


def test_case_inspection_retains_final_checker_observability_gap():
    result = inspector.inspect_case(inspector.DEFAULT_ROOT, "b0006", "rerun")
    assert result["investigation"]["result"] is None
    assert any(
        e["sequence"] == 89 and e["payload"].get("reason") == "unsupported_explanation"
        for e in result["events"]
    )
    with pytest.raises(ValueError, match="Unknown case"):
        inspector.inspect_case(inspector.DEFAULT_ROOT, "../manifest", "rerun")


def test_excluded_apollo_passage_is_present_and_not_supplied():
    data = inspector.read(inspector.DEFAULT_ROOT / "apollo-selection.json")
    assert len(data["supplied_spans"]) == 120
    excluded = data["excluded_relevant_span"]
    assert excluded["id"] == 241
    assert "July 20, 1969" in excluded["text"]
    assert excluded["id"] not in {s["id"] for s in data["supplied_spans"]}


def test_runtime_archive_matches_its_per_file_provenance():
    root = inspector.DEFAULT_ROOT / "rerun-runtime"
    provenance = inspector.read(root / "provenance.json")
    for path, expected in provenance["files_sha256"].items():
        assert inspector.hashlib.sha256((root / path).read_bytes()).hexdigest() == expected
