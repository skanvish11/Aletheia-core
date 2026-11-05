"""Tests for evals/validate.py. Run: python -m unittest discover -s evals"""

from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import validate

EXAMPLES = json.loads(
    (validate.EVALS / "examples" / "example-claims.json").read_text(encoding="utf-8")
)
EXAMPLE = EXAMPLES[0]
ALMOST = EXAMPLE["acceptable_alternatives"][0]
UNDECIDED = EXAMPLES[1]["expected"]
TRUE = EXAMPLE["expected"]


def reconciled(**changes):
    record = copy.deepcopy(EXAMPLE)
    record.update(changes)
    return record


def draft(labeler="pari", **changes):
    return reconciled(labelers=[labeler], status="draft", **changes)


class Checks(unittest.TestCase):
    def setUp(self):
        self.checker = validate.SchemaChecker(validate.load_schema())

    def errors(self, record):
        schema = self.checker.check(record, self.checker.root, "")
        return schema + validate.record_rules(record, in_claims_file=True)

    def joined(self, record):
        return " | ".join(self.errors(record))


class SchemaTests(Checks):
    def test_examples_are_valid(self):
        for record in EXAMPLES:
            self.assertEqual(self.errors(record), [], record["id"])

    def test_missing_required_field(self):
        record = reconciled()
        del record["as_of"]
        self.assertIn("missing required field 'as_of'", self.joined(record))

    def test_unknown_field_rejected(self):
        self.assertIn(
            "unknown field 'expected_verdict'", self.joined(reconciled(expected_verdict="true"))
        )

    def test_old_verdicts_rejected(self):
        for old in ("supported", "mixed", "insufficient_evidence"):
            record = reconciled(expected=dict(TRUE, verdict=old))
            self.assertIn("expected.verdict", self.joined(record), old)

    def test_unknown_flag_dimension(self):
        flag = {"type": "misleading_comparison", "dimension": "vibes", "rationale": "long enough"}
        self.assertIn("dimension", self.joined(reconciled(expected_flags=[flag])))

    def test_ai_claim_dimensions_accepted(self):
        flags = [
            {
                "type": "misleading_comparison",
                "dimension": "evaluation_setup",
                "rationale": "CoT@32 vs 5-shot",
            },
            {
                "type": "narrow_scope",
                "dimension": "benchmark_subset",
                "rationale": "a subset of the benchmark",
            },
        ]
        self.assertEqual(self.errors(reconciled(expected_flags=flags)), [])

    def test_key_sources_bounds(self):
        self.assertIn("at least 1", self.joined(reconciled(key_sources=[])))
        source = EXAMPLE["key_sources"][0]
        four = [dict(source, url=f"https://example.com/{i}") for i in range(4)]
        self.assertIn("at most 3", self.joined(reconciled(key_sources=four)))

    def test_bad_url(self):
        bad = [{"url": "example.com/x", "shows": "something specific"}]
        self.assertIn("does not match", self.joined(reconciled(key_sources=bad)))

    def test_dates_must_be_exactly_yyyy_mm_dd(self):
        # Python 3.11+ fromisoformat also accepts these; the contract does not.
        for value in ("20261104", "2026-W45-3", "04/11/2026", "2026-11-4"):
            self.assertIn("YYYY-MM-DD", self.joined(reconciled(as_of=value)), value)
        self.assertEqual(self.errors(reconciled(as_of="2026-11-04")), [])

    def test_future_as_of(self):
        self.assertIn("as_of: date is in the future", self.errors(reconciled(as_of="2999-01-01")))


class DecisionTests(Checks):
    def test_undecided_needs_reason_and_null_verdict(self):
        record = reconciled(expected=dict(UNDECIDED, verdict="false"))
        self.assertIn("unable_to_decide needs a reason and a null verdict", self.joined(record))
        record = reconciled(expected=dict(UNDECIDED, unable_to_decide_reason=None))
        self.assertIn("unable_to_decide needs a reason", self.joined(record))

    def test_decided_needs_verdict_and_no_reason(self):
        record = reconciled(expected=dict(TRUE, unable_to_decide_reason="insufficient_evidence"))
        self.assertIn("a decided outcome needs a verdict and a null reason", self.joined(record))
        record = reconciled(expected=dict(TRUE, verdict=None))
        self.assertIn("a decided outcome needs a verdict", self.joined(record))

    def test_almost_requires_expected_correction(self):
        record = reconciled(
            expected=dict(ALMOST, expected_correction=None), acceptable_alternatives=[]
        )
        self.assertIn("an almost verdict needs an expected_correction", self.joined(record))

    def test_correction_only_for_almost(self):
        record = reconciled(expected=dict(TRUE, expected_correction=ALMOST["expected_correction"]))
        self.assertIn("only an almost verdict has an expected_correction", self.joined(record))

    def test_correction_parts_required(self):
        partial = {"what_is_correct": "The core figure is right."}
        record = reconciled(acceptable_alternatives=[dict(ALMOST, expected_correction=partial)])
        self.assertIn("missing required field 'corrected_claim'", self.joined(record))

    def test_alternatives_must_not_repeat_expected_or_each_other(self):
        self.assertIn(
            "must not repeat the expected decision",
            self.joined(reconciled(acceptable_alternatives=[TRUE])),
        )
        self.assertIn(
            "appears twice", self.joined(reconciled(acceptable_alternatives=[ALMOST, ALMOST]))
        )

    def test_duplicate_flag(self):
        flag = EXAMPLE["expected_flags"][0]
        record = reconciled(expected_flags=[flag, dict(flag, rationale="another long rationale")])
        self.assertIn("the same type and dimension appears twice", self.joined(record))

    def test_reconciled_needs_two_labelers(self):
        self.assertIn("two labelers", self.joined(reconciled(labelers=["pari"])))

    def test_claims_file_rejects_drafts(self):
        self.assertIn("not drafts", self.joined(draft()))


class MalformedTypeTests(Checks):
    """Wrong types are reported by the schema check; cross-field rules must not crash."""

    CASES = {
        "acceptable_alternatives": None,
        "expected_flags": None,
        "labelers": None,
        "id": [],
        "expected": "true",
        "as_of": 20261104,
    }

    def test_each_malformed_field_is_reported_without_crashing(self):
        for field, value in self.CASES.items():
            with self.subTest(field=field):
                self.assertIn(field, self.joined(reconciled(**{field: value})))

    def test_malformed_record_does_not_stop_later_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.json"
            bad = reconciled(id=[], labelers=None, acceptable_alternatives=None)
            path.write_text(
                json.dumps([bad, reconciled(id="second", as_of="bad")]), encoding="utf-8"
            )
            errors = " | ".join(validate.validate_path(path, self.checker))
        self.assertIn("#0", errors)
        self.assertIn("second: as_of", errors)

    def test_malformed_label_file_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "labels" / "pari" / "example-northwind.json"
            path.parent.mkdir(parents=True)
            record = reconciled(status="draft", expected_flags=None, labelers=None)
            path.write_text(json.dumps(record), encoding="utf-8")
            errors = " | ".join(validate.validate_path(path, self.checker))
        self.assertIn("expected_flags", errors)
        self.assertIn("labelers", errors)


class FileTests(Checks):
    def setUp(self):
        super().setUp()
        self.tmp = Path(tempfile.mkdtemp())

    def write(self, rel, data):
        path = self.tmp / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def run_main(self, *paths):
        out = io.StringIO()
        with redirect_stdout(out):
            code = validate.main([str(p) for p in paths])
        return code, out.getvalue()

    def test_valid_label_file(self):
        path = self.write("labels/pari/example-northwind.json", draft())
        self.assertEqual(validate.validate_path(path, self.checker), [])

    def test_array_under_labels_is_rejected_through_main(self):
        # Regression: content-based dispatch let an array in labels/ skip the label rules.
        path = self.write("labels/pari/wrong-id.json", [reconciled()])
        code, out = self.run_main(path)
        self.assertEqual(code, 1)
        self.assertIn("one draft record", out)

    def test_label_file_name_and_folder_must_match(self):
        path = self.write("labels/sai/other-id.json", draft(labeler="pari"))
        errors = " | ".join(validate.validate_path(path, self.checker))
        self.assertIn("must match the file name", errors)
        self.assertIn("to match the folder", errors)

    def test_label_file_must_be_draft(self):
        path = self.write("labels/pari/example-northwind.json", reconciled(labelers=["pari"]))
        self.assertIn("must be 'draft'", " | ".join(validate.validate_path(path, self.checker)))

    def test_claims_file_must_be_an_array(self):
        path = self.write("claims.json", reconciled())
        code, out = self.run_main(path)
        self.assertEqual(code, 1)
        self.assertIn("must be a JSON array", out)

    def test_claims_file_duplicate_ids(self):
        path = self.write("claims.json", [reconciled(), reconciled()])
        self.assertIn("duplicate id", " | ".join(validate.validate_path(path, self.checker)))

    def test_invalid_json_reported(self):
        path = self.tmp / "claims.json"
        path.write_text("[{", encoding="utf-8")
        self.assertIn("cannot read JSON", " | ".join(validate.validate_path(path, self.checker)))

    def test_main_passes_on_valid_files(self):
        code, out = self.run_main(
            self.write("claims.json", EXAMPLES),
            self.write("labels/pari/example-northwind.json", draft()),
        )
        self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main()
