"""Verify citation and terminal-transaction protections detect deliberate faults offline."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    (
        "provider trace is not persisted",
        "orchestrator.py",
        "budget.observer = observe",
        "budget.observer = None",
        "tests/test_adversarial_evaluation_trace.py::test_non_model_failure_trace_survives_restart[search-503]",
    ),
    (
        "schema diagnostics leak untrusted extra field names",
        "providers/nebius.py",
        'and e["loc"][0] in response_type.model_fields',
        "",
        "tests/test_adversarial_evaluation_trace.py::test_invalid_completion_keeps_usage_and_safe_reason_not_private_keys[schema]",
    ),
    (
        "duplicate search hits consume counterevidence selection turns",
        "research.py",
        "if key in ranked_keys:",
        "if key in seen_urls:",
        "tests/test_adversarial_step4.py::test_overlapping_top_hits_do_not_crowd_out_counterevidence",
    ),
    (
        "refresh selection omits the contradicting side",
        "research.py",
        'for relation in ("supports", "contradicts"):',
        'for relation in ("supports",):',
        "tests/test_adversarial_step4.py::test_refresh_rechecks_both_sides_of_a_previously_conflicting_finding",
    ),
    (
        "refresh drops cited baseline evidence",
        "orchestrator.py",
        "baseline_sources if round_index == 0 else (),",
        "(),",
        "tests/test_step4_review.py::test_refresh_rechecks_cited_pages_when_rankings_shift[False]",
    ),
    (
        "rejected rationale reaches planning",
        "research_gate.py",
        '"rationale": assessment.rationale[:600] if item.admissible else None,',
        '"rationale": assessment.rationale[:600],',
        "tests/test_step4_review.py::test_planning_context_excludes_rejected_passage_and_rationale",
    ),
    (
        "first round consumes follow-up page capacity",
        "orchestrator.py",
        'page_limit=2 if assigned_route == "quick" or round_index else 4,',
        "page_limit=None,",
        "tests/test_deeper_research.py::test_large_source_lists_leave_capacity_for_two_followups_and_finalization",
    ),
    (
        "conflict hidden by a retrieval gap",
        "research_gate.py",
        'if computed.unable_to_decide_reason == "conflicting_evidence":',
        'if computed.unable_to_decide_reason == "conflicting_evidence" and not retrieval_gap:',
        "tests/test_deeper_research.py::test_conflict_takes_priority_over_retrieval_gap_and_can_stop_honestly",
    ),
    (
        "finalization reserve cannot cover both repairs",
        "budgets.py",
        "self.reserve_model_attempts = 4",
        "self.reserve_model_attempts = 3",
        "tests/test_research_review.py::test_finalization_reserve_covers_repairs_to_both_model_tasks",
    ),
    (
        "explicit retry rejects failed investigations",
        "storage.py",
        'if parent["status"] != "failed" and not (',
        "if not (",
        "tests/test_research_review.py::test_failed_run_has_explicit_idempotent_retry[False]",
    ),
    (
        "Almost semantic correction check bypassed",
        "verdicts.py",
        "        if not all(\n",
        "        if False and not all(\n",
        "tests/test_verdict_labels.py::test_each_failed_correction_check_prevents_almost[corrected_claim_supported]",
    ),
    (
        "cross-snapshot citation accepted",
        "evidence.py",
        "if assessment.citation.snapshot_id != source.id:",
        "if False:",
        "tests/test_research_integrity.py::test_snapshot_identity_and_provenance_validation",
    ),
    (
        "terminal state committed before its event",
        "storage.py",
        "                if comparison:\n",
        "                await db.commit()\n                if comparison:\n",
        "tests/test_research_integrity.py::test_atomic_completion_rollback_and_append_only_records",
    ),
    (
        "research consumes finalization reserve",
        "budgets.py",
        'if not self.finalizing and operation == "model":',
        "if False:",
        "tests/test_research_pipeline.py::test_finalization_reserve_and_escalation_are_shared",
    ),
)


def main():
    for name, filename, old, new, test in MUTATIONS:
        with tempfile.TemporaryDirectory(prefix="aletheia-research-mutation-") as directory:
            work = Path(directory)
            for folder in ("src", "tests"):
                shutil.copytree(
                    ROOT / folder, work / folder, ignore=shutil.ignore_patterns("__pycache__")
                )
            shutil.copy2(ROOT / "pyproject.toml", work / "pyproject.toml")
            target = work / "src/aletheia" / filename
            original = target.read_text()
            if original.count(old) != 1:
                raise SystemExit("Expected exactly one mutation target.")
            target.write_text(original.replace(old, new, 1))
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", test],
                cwd=work,
                env={**os.environ, "PYTHONPATH": str(work / "src")},
                text=True,
                capture_output=True,
                timeout=30,
            )
            if result.returncode != 1 or "1 failed" not in result.stdout:
                print(result.stdout)
                print(result.stderr, file=sys.stderr)
                raise SystemExit(f"Expected test failure was not observed: {name}")
            print(f"DETECTED: {name}")


if __name__ == "__main__":
    main()
