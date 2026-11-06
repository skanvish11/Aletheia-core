"""Prove budget and schema tests catch deliberate faults in temporary source copies."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    (
        "provider budget disabled",
        "budgets.py",
        "if self.used[operation] + units > limit:",
        "if False:",
        "tests/test_providers.py::test_retry_cannot_dispatch_after_budget_exhausted",
    ),
    (
        "model types silently coerced",
        "providers/nebius.py",
        "parse_json(choice.message.content), strict=True",
        "parse_json(choice.message.content), strict=False",
        "tests/test_providers.py::test_json_object_mode_still_validates_locally",
    ),
)


def main() -> None:
    for name, filename, old, new, test in MUTATIONS:
        with tempfile.TemporaryDirectory(prefix="aletheia-provider-mutation-") as directory:
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
