"""Confirm two critical regression tests reject deliberate faults in temporary copies."""

import ast
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


def mutate_submission(source: str, old: str, new: str) -> str:
    """Alter exactly one intended expression inside Storage.submit, or fail closed."""
    tree = ast.parse(source)
    storage = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Storage"
    )
    submission = next(
        node
        for node in storage.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "submit"
    )
    lines = source.splitlines(keepends=True)
    body = "".join(lines[submission.lineno - 1 : submission.end_lineno])
    if body.count(old) != 1:
        raise ValueError("Mutation must match exactly once inside Storage.submit.")
    return (
        "".join(lines[: submission.lineno - 1])
        + body.replace(old, new, 1)
        + "".join(lines[submission.end_lineno :])
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
            target.write_text(mutate_submission(original, old, new))
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
