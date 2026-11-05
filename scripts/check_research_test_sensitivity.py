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
