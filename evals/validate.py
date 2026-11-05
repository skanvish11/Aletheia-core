"""Validate Aletheia eval claim records. Standard library only.

Usage:
    python evals/validate.py            # claims.json and every file under labels/
    python evals/validate.py FILE...    # specific files

Structural rules come from schema/claim.schema.json, which this script interprets
(it supports the subset of JSON Schema that file uses). Rules a schema can't
express, such as labeler counts per status, are checked in code below.
Exit status is 1 if any record is invalid.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any

EVALS = Path(__file__).resolve().parent
SCHEMA_PATH = EVALS / "schema" / "claim.schema.json"
CLAIMS_PATH = EVALS / "claims.json"
LABELS_DIR = EVALS / "labels"

TYPE_CHECKS = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
}


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


class SchemaChecker:
    """Checks a value against the JSON Schema subset used by claim.schema.json."""

    def __init__(self, schema: dict[str, Any]):
        self.root = schema

    def resolve(self, node: dict[str, Any]) -> dict[str, Any]:
        while "$ref" in node:
            ref = node["$ref"]
            if not ref.startswith("#/"):
                raise ValueError(f"unsupported $ref {ref}")
            target: Any = self.root
            for part in ref[2:].split("/"):
                target = target[part]
            node = target
        return node

    def check(self, value: Any, node: dict[str, Any], path: str) -> list[str]:
        node = self.resolve(node)
        errors: list[str] = []

        if "enum" in node and value not in node["enum"]:
            return [f"{path}: {value!r} is not one of {', '.join(map(str, node['enum']))}"]

        expected_type = node.get("type")
        if expected_type and not TYPE_CHECKS[expected_type](value):
            return [f"{path}: expected {expected_type}, got {type(value).__name__}"]

        if isinstance(value, str):
            if "minLength" in node and len(value.strip()) < node["minLength"]:
                errors.append(f"{path}: must be at least {node['minLength']} characters")
            if "maxLength" in node and len(value) > node["maxLength"]:
                errors.append(f"{path}: must be at most {node['maxLength']} characters")
            if "pattern" in node and not re.search(node["pattern"], value):
                errors.append(f"{path}: {value!r} does not match {node['pattern']}")
            if node.get("format") == "date":
                try:
                    dt.date.fromisoformat(value)
                except ValueError:
                    errors.append(f"{path}: {value!r} is not a YYYY-MM-DD date")

        if isinstance(value, list):
            if "minItems" in node and len(value) < node["minItems"]:
                errors.append(f"{path}: needs at least {node['minItems']} item(s)")
            if "maxItems" in node and len(value) > node["maxItems"]:
                errors.append(f"{path}: allows at most {node['maxItems']} item(s)")
            if node.get("uniqueItems"):
                seen = [json.dumps(v, sort_keys=True) for v in value]
                if len(seen) != len(set(seen)):
                    errors.append(f"{path}: items must be unique")
            if "items" in node:
                for i, item in enumerate(value):
                    errors += self.check(item, node["items"], f"{path}[{i}]")

        if isinstance(value, dict):
            props = node.get("properties", {})
            for key in node.get("required", []):
                if key not in value:
                    errors.append(f"{path}: missing required field {key!r}")
            if node.get("additionalProperties") is False:
                for key in value:
                    if key not in props:
                        errors.append(f"{path}: unknown field {key!r}")
            for key, sub in props.items():
                if key in value:
                    errors += self.check(value[key], sub, f"{path}.{key}" if path else key)

        return errors


def record_rules(record: dict[str, Any], *, in_claims_file: bool) -> list[str]:
    """Cross-field rules the schema can't express."""
    errors: list[str] = []
    status = record.get("status")
    labelers = record.get("labelers", [])

    if record.get("expected_verdict") in record.get("acceptable_verdicts", []):
        errors.append("acceptable_verdicts: must not repeat expected_verdict")

    pairs = [(f.get("type"), f.get("dimension")) for f in record.get("expected_flags", []) if isinstance(f, dict)]
    if len(pairs) != len(set(pairs)):
        errors.append("expected_flags: the same type and dimension appears twice")

    if status == "draft" and len(labelers) != 1:
        errors.append("labelers: a draft (blind label) has exactly one labeler")
    if status in ("reconciled", "contested") and len(labelers) < 2:
        errors.append(f"labelers: a {status} record needs at least two labelers")
    if in_claims_file and status == "draft":
        errors.append("status: claims.json holds reconciled or contested records, not drafts")

    as_of = record.get("as_of")
    if isinstance(as_of, str):
        try:
            if dt.date.fromisoformat(as_of) > dt.date.today():
                errors.append("as_of: date is in the future")
        except ValueError:
            pass  # already reported by the schema check
    return errors


def label_file_rules(record: dict[str, Any], path: Path) -> list[str]:
    """A blind label lives at labels/<labeler>/<id>.json."""
    errors: list[str] = []
    if record.get("id") != path.stem:
        errors.append(f"id: {record.get('id')!r} must match the file name {path.stem!r}")
    if record.get("labelers") != [path.parent.name]:
        errors.append(f"labelers: must be [{path.parent.name!r}] to match the folder")
    if record.get("status") != "draft":
        errors.append("status: blind label files must be 'draft'")
    return errors


def load_json(path: Path) -> tuple[Any, list[str]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"cannot read JSON: {exc}"]


def validate_claims_file(path: Path, checker: SchemaChecker) -> list[str]:
    data, errors = load_json(path)
    if errors:
        return [f"{path.name}: {e}" for e in errors]
    if not isinstance(data, list):
        return [f"{path.name}: must be a JSON array of claim records"]
    out: list[str] = []
    seen: set[str] = set()
    for i, record in enumerate(data):
        rid = record.get("id", f"#{i}") if isinstance(record, dict) else f"#{i}"
        problems = checker.check(record, checker.root, "")
        if isinstance(record, dict):
            problems += record_rules(record, in_claims_file=True)
            if rid in seen:
                problems.append("id: duplicate id")
            seen.add(rid)
        out += [f"{path.name}: {rid}: {p}" for p in problems]
    return out


def validate_label_file(path: Path, checker: SchemaChecker) -> list[str]:
    record, errors = load_json(path)
    if not errors:
        errors = checker.check(record, checker.root, "")
        if isinstance(record, dict):
            errors += record_rules(record, in_claims_file=False) + label_file_rules(record, path)
    shown = path.relative_to(EVALS) if path.is_relative_to(EVALS) else path
    return [f"{shown}: {e}" for e in errors]


def main(argv: list[str]) -> int:
    checker = SchemaChecker(load_schema())
    if argv:
        paths = [Path(a).resolve() for a in argv]
    else:
        paths = ([CLAIMS_PATH] if CLAIMS_PATH.exists() else []) + sorted(LABELS_DIR.glob("*/*.json"))

    errors: list[str] = []
    for path in paths:
        # An array is a set of reconciled records (claims.json, examples/);
        # a single object is one labeler's blind label.
        data, _ = load_json(path)
        if isinstance(data, list):
            errors += validate_claims_file(path, checker)
        else:
            errors += validate_label_file(path, checker)

    for line in errors:
        print(line)
    print(f"{len(paths)} file(s) checked, {len(errors)} problem(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
