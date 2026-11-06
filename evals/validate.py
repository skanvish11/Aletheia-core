"""Validate Aletheia eval claim records. Standard library only.

Usage:
    python evals/validate.py            # claims.json (required) and every JSON file under labels/
    python evals/validate.py FILE...    # specific files

Structural rules come from schema/claim.schema.json, which this script interprets
(it supports the subset of JSON Schema that file uses). Rules a schema can't
express, such as labeler counts per status or decision consistency, are checked in
code below. A file's location decides its kind: anything under evals/labels/ is one
labeler's single draft record and must sit at labels/<labeler>/<id>.json; every
other file is an array of reconciled records.
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

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

TYPE_CHECKS = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "null": lambda v: v is None,
}


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def parse_date(value: str) -> dt.date | None:
    """Strict YYYY-MM-DD only; fromisoformat alone also accepts 20261104 and 2026-W45-3."""
    if not DATE_RE.match(value):
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


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
        where = path or "record"

        if "enum" in node and value not in node["enum"]:
            options = ", ".join("null" if o is None else str(o) for o in node["enum"])
            return [f"{where}: {value!r} is not one of {options}"]

        expected = node.get("type")
        if expected:
            types = expected if isinstance(expected, list) else [expected]
            if not any(TYPE_CHECKS[t](value) for t in types):
                return [f"{where}: expected {' or '.join(types)}, got {type(value).__name__}"]
            if value is None:
                return []

        errors: list[str] = []
        if isinstance(value, str):
            errors += self._check_string(value, node, where)
        if isinstance(value, list):
            errors += self._check_array(value, node, where)
        if isinstance(value, dict):
            errors += self._check_object(value, node, path)
        return errors

    def _check_string(self, value: str, node: dict[str, Any], where: str) -> list[str]:
        errors = []
        if "minLength" in node and len(value.strip()) < node["minLength"]:
            errors.append(f"{where}: must be at least {node['minLength']} characters")
        if "maxLength" in node and len(value) > node["maxLength"]:
            errors.append(f"{where}: must be at most {node['maxLength']} characters")
        if "pattern" in node and not re.search(node["pattern"], value):
            errors.append(f"{where}: {value!r} does not match {node['pattern']}")
        if node.get("format") == "date" and parse_date(value) is None:
            errors.append(f"{where}: {value!r} is not a YYYY-MM-DD date")
        return errors

    def _check_array(self, value: list[Any], node: dict[str, Any], where: str) -> list[str]:
        errors = []
        if "minItems" in node and len(value) < node["minItems"]:
            errors.append(f"{where}: needs at least {node['minItems']} item(s)")
        if "maxItems" in node and len(value) > node["maxItems"]:
            errors.append(f"{where}: allows at most {node['maxItems']} item(s)")
        if node.get("uniqueItems"):
            seen = [json.dumps(v, sort_keys=True) for v in value]
            if len(seen) != len(set(seen)):
                errors.append(f"{where}: items must be unique")
        if "items" in node:
            for i, item in enumerate(value):
                errors += self.check(item, node["items"], f"{where}[{i}]")
        return errors

    def _check_object(self, value: dict[str, Any], node: dict[str, Any], path: str) -> list[str]:
        errors = []
        where = path or "record"
        props = node.get("properties", {})
        for key in node.get("required", []):
            if key not in value:
                errors.append(f"{where}: missing required field {key!r}")
        if node.get("additionalProperties") is False:
            errors += [f"{where}: unknown field {key!r}" for key in value if key not in props]
        for key, sub in props.items():
            if key in value:
                errors += self.check(value[key], sub, f"{path}.{key}" if path else key)
        return errors


def _list(value: Any) -> list[Any]:
    """Cross-field rules only trust values the schema check could have accepted."""
    return value if isinstance(value, list) else []


def decision_rules(decision: Any, where: str) -> list[str]:
    """Mirrors the research Decision contract; skips anything already mistyped."""
    if not isinstance(decision, dict):
        return []
    errors = []
    outcome = decision.get("outcome")
    verdict = decision.get("verdict")
    reason = decision.get("unable_to_decide_reason")
    correction = decision.get("expected_correction")
    if outcome == "unable_to_decide" and (verdict is not None or reason is None):
        errors.append(f"{where}: unable_to_decide needs a reason and a null verdict")
    if outcome == "decided" and (verdict is None or reason is not None):
        errors.append(f"{where}: a decided outcome needs a verdict and a null reason")
    if verdict == "almost" and not isinstance(correction, dict):
        errors.append(f"{where}: an almost verdict needs an expected_correction")
    if verdict != "almost" and correction is not None:
        errors.append(f"{where}: only an almost verdict has an expected_correction")
    return errors


def _scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _decision_key(decision: Any) -> tuple[Any, ...] | None:
    """A decision's comparable identity, or None if a part is mistyped (the schema reports it)."""
    if not isinstance(decision, dict):
        return None
    key = tuple(decision.get(k) for k in ("outcome", "verdict", "unable_to_decide_reason"))
    return key if all(_scalar(part) for part in key) else None


def _normalized(text: str) -> str:
    return " ".join(text.split()).casefold()


def _unchanged_correction(decision: Any, claim: Any) -> bool:
    """An Almost correction whose corrected claim just restates the claim corrects nothing."""
    if not isinstance(decision, dict) or not isinstance(claim, str):
        return False
    correction = decision.get("expected_correction")
    corrected = correction.get("corrected_claim") if isinstance(correction, dict) else None
    return isinstance(corrected, str) and _normalized(corrected) == _normalized(claim)


def record_rules(record: dict[str, Any], *, in_claims_file: bool) -> list[str]:
    """Cross-field rules the schema can't express. Mistyped fields are skipped, not crashed on."""
    errors: list[str] = []
    status = record.get("status")
    labelers = _list(record.get("labelers"))

    errors += decision_rules(record.get("expected"), "expected")
    alternatives = _list(record.get("acceptable_alternatives"))
    for i, alternative in enumerate(alternatives):
        errors += decision_rules(alternative, f"acceptable_alternatives[{i}]")
    named = [("expected", record.get("expected"))] + [
        (f"acceptable_alternatives[{i}]", a) for i, a in enumerate(alternatives)
    ]
    for where, decision in named:
        if _unchanged_correction(decision, record.get("claim")):
            errors.append(f"{where}: expected_correction.corrected_claim repeats the claim")
    expected_key = _decision_key(record.get("expected"))
    keys = [_decision_key(a) for a in alternatives]
    if expected_key is not None and expected_key in keys:
        errors.append("acceptable_alternatives: must not repeat the expected decision")
    known = [k for k in keys if k is not None]
    if len(known) != len(set(known)):
        errors.append("acceptable_alternatives: the same decision appears twice")

    flags = [f for f in _list(record.get("expected_flags")) if isinstance(f, dict)]
    pairs = [(f.get("type"), f.get("dimension")) for f in flags]
    pairs = [p for p in pairs if all(_scalar(part) for part in p)]
    if len(pairs) != len(set(pairs)):
        errors.append("expected_flags: the same type and dimension appears twice")

    if status == "draft" and len(labelers) != 1:
        errors.append("labelers: a draft (blind label) has exactly one labeler")
    if status in ("reconciled", "contested") and len(labelers) < 2:
        errors.append(f"labelers: a {status} record needs at least two labelers")
    if in_claims_file and status == "draft":
        errors.append("status: claims.json holds reconciled or contested records, not drafts")

    as_of = record.get("as_of")
    date = parse_date(as_of) if isinstance(as_of, str) else None
    if date is not None and date > dt.date.today():
        errors.append("as_of: date is in the future")
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


def _shown(path: Path) -> str:
    return str(path.relative_to(EVALS)) if path.is_relative_to(EVALS) else path.name


def validate_claims_file(path: Path, checker: SchemaChecker) -> list[str]:
    data, errors = load_json(path)
    name = _shown(path)
    if errors:
        return [f"{name}: {e}" for e in errors]
    if not isinstance(data, list):
        return [f"{name}: must be a JSON array of claim records"]
    out: list[str] = []
    seen: set[str] = set()
    for i, record in enumerate(data):
        rid = record.get("id") if isinstance(record, dict) else None
        label = rid if isinstance(rid, str) else f"#{i}"
        problems = checker.check(record, checker.root, "")
        if isinstance(record, dict):
            problems += record_rules(record, in_claims_file=True)
            if isinstance(rid, str):
                if rid in seen:
                    problems.append("id: duplicate id")
                seen.add(rid)
        out += [f"{name}: {label}: {p}" for p in problems]
    return out


def validate_label_file(path: Path, checker: SchemaChecker, labels_dir: Path) -> list[str]:
    shown = _shown(path)
    if len(path.relative_to(labels_dir).parts) != 2:
        return [f"{shown}: label files must be at labels/<labeler>/<id>.json"]
    record, errors = load_json(path)
    if not errors:
        if not isinstance(record, dict):
            errors = ["a label file holds one draft record (a JSON object), not an array"]
        else:
            errors = checker.check(record, checker.root, "")
            errors += record_rules(record, in_claims_file=False)
            errors += label_file_rules(record, path)
    return [f"{shown}: {e}" for e in errors]


def validate_path(path: Path, checker: SchemaChecker, evals_dir: Path = EVALS) -> list[str]:
    """Location, not content, decides the kind: anything under <evals>/labels/ is a label."""
    labels_dir = (evals_dir / "labels").resolve()
    path = path.resolve()
    if path.is_relative_to(labels_dir):
        return validate_label_file(path, checker, labels_dir)
    return validate_claims_file(path, checker)


def default_files(evals_dir: Path) -> tuple[list[Path], list[str]]:
    """claims.json (required, may be []) and every JSON file anywhere under labels/."""
    claims = evals_dir / "claims.json"
    labels = evals_dir / "labels"
    files = [claims] if claims.exists() else []
    missing = [] if claims.exists() else ["claims.json: required file is missing (use [] if empty)"]
    if labels.is_dir():
        files += sorted(p for p in labels.rglob("*") if p.is_file() and p.suffix.lower() == ".json")
    return files, missing


def main(argv: list[str], evals_dir: Path = EVALS) -> int:
    checker = SchemaChecker(load_schema())
    if argv:
        paths, errors = [Path(a) for a in argv], []
    else:
        paths, errors = default_files(evals_dir)

    errors += [line for path in paths for line in validate_path(path, checker, evals_dir)]
    for line in errors:
        print(line)
    print(f"{len(paths)} file(s) checked, {len(errors)} problem(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
