"""Confirm two critical regression tests reject deliberate faults in temporary copies."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    (
        "duplicate lookup disabled",
        "WHERE c.request_key = ? ORDER BY",
        "WHERE c.request_key = ? AND 0 ORDER BY",
        "tests/test_api.py::test_submit_retrieve_and_duplicate",
    ),
    (
        "failed transaction committed",
        "await db.rollback()",
        "await db.commit()",
        "tests/test_storage.py::test_failed_event_rolls_back_entire_submission",
    ),
)


def main() -> None:
    for name, old, new, test in MUTATIONS:
        with tempfile.TemporaryDirectory(prefix="aletheia-mutation-") as directory:
            work = Path(directory)
            for folder in ("src", "tests"):
                shutil.copytree(
                    ROOT / folder, work / folder, ignore=shutil.ignore_patterns("__pycache__")
                )
            shutil.copy2(ROOT / "pyproject.toml", work / "pyproject.toml")
            target = work / "src/aletheia/storage.py"
            original = target.read_text()
            if old not in original:
                raise SystemExit(f"Mutation target changed: {name}")
            target.write_text(original.replace(old, new))
            environment = {**os.environ, "PYTHONPATH": str(work / "src")}
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", test],
                cwd=work,
                env=environment,
                text=True,
                capture_output=True,
                timeout=30,
            )
            if (
                result.returncode != 1
                or "AssertionError" not in result.stdout
                or "1 failed" not in result.stdout
            ):
                print(result.stdout)
                print(result.stderr, file=sys.stderr)
                raise SystemExit(f"Expected assertion failure was not observed: {name}")
            print(f"DETECTED: {name} ({test})")


if __name__ == "__main__":
    main()
