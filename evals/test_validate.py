"""Tests for evals/validate.py. Run: python -m unittest discover -s evals"""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

import validate

EXAMPLE = json.loads((validate.EVALS / "examples" / "example-claims.json").read_text(encoding="utf-8"))[0]


def reconciled(**changes):
    record = copy.deepcopy(EXAMPLE)
    record.update(changes)
    return record


def draft(labeler="pari", **changes):
    return reconciled(labelers=[labeler], status="draft", **changes)


class SchemaTests(unittest.TestCase):
    def setUp(self):
        self.checker = validate.SchemaChecker(validate.load_schema())

    def errors(self, record):
        return self.checker.check(record, self.checker.root, "") + validate.record_rules(
            record, in_claims_file=True
        )

    def test_example_is_valid(self):
        self.assertEqual(self.errors(reconciled()), [])

    def test_missing_required_field(self):
        record = reconciled()
        del record["as_of"]
        self.assertIn("missing required field 'as_of'", " ".join(self.errors(record)))

    def test_unknown_field_rejected(self):
        self.assertIn("unknown field 'verdict'", " ".join(self.errors(reconciled(verdict="supported"))))

    def test_unknown_verdict(self):
        self.assertTrue(any("expected_verdict" in e for e in self.errors(reconciled(expected_verdict="true"))))

    def test_unknown_flag_dimension(self):
        flag = {"type": "misleading_comparison", "dimension": "vibes", "rationale": "a long enough reason"}
        self.assertTrue(any("dimension" in e for e in self.errors(reconciled(expected_flags=[flag]))))

    def test_ai_claim_dimensions_accepted(self):
        flags = [
            {"type": "misleading_comparison", "dimension": "evaluation_setup", "rationale": "CoT@32 vs 5-shot scores"},
            {"type": "narrow_scope", "dimension": "benchmark_subset", "rationale": "result on a benchmark subset"},
        ]
        self.assertEqual(self.errors(reconciled(expected_flags=flags)), [])

    def test_key_sources_bounds(self):
        self.assertTrue(any("at least 1" in e for e in self.errors(reconciled(key_sources=[]))))
        source = EXAMPLE["key_sources"][0]
        four = [dict(source, url=f"https://example.com/{i}") for i in range(4)]
        self.assertTrue(any("at most 3" in e for e in self.errors(reconciled(key_sources=four))))

    def test_bad_url_and_date(self):
        bad = [{"url": "example.com/x", "shows": "something specific"}]
        self.assertTrue(any("does not match" in e for e in self.errors(reconciled(key_sources=bad))))
        self.assertTrue(any("YYYY-MM-DD" in e for e in self.errors(reconciled(as_of="04/11/2026"))))

    def test_future_as_of(self):
        self.assertIn("as_of: date is in the future", self.errors(reconciled(as_of="2999-01-01")))

    def test_acceptable_must_not_repeat_expected(self):
        record = reconciled(acceptable_verdicts=["supported"])
        self.assertIn("acceptable_verdicts: must not repeat expected_verdict", self.errors(record))

    def test_duplicate_flag(self):
        flag = EXAMPLE["expected_flags"][0]
        record = reconciled(expected_flags=[flag, dict(flag, rationale="another long rationale")])
        self.assertIn("expected_flags: the same type and dimension appears twice", self.errors(record))

    def test_reconciled_needs_two_labelers(self):
        self.assertTrue(any("two labelers" in e for e in self.errors(reconciled(labelers=["pari"]))))

    def test_claims_file_rejects_drafts(self):
        self.assertTrue(any("not drafts" in e for e in self.errors(draft())))


class FileTests(unittest.TestCase):
    def setUp(self):
        self.checker = validate.SchemaChecker(validate.load_schema())
        self.tmp = Path(tempfile.mkdtemp())

    def write(self, rel, data):
        path = self.tmp / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_valid_label_file(self):
        path = self.write("labels/pari/example-northwind.json", draft())
        self.assertEqual(validate.validate_label_file(path, self.checker), [])

    def test_label_file_name_and_folder_must_match(self):
        path = self.write("labels/sai/other-id.json", draft(labeler="pari"))
        errors = " ".join(validate.validate_label_file(path, self.checker))
        self.assertIn("must match the file name", errors)
        self.assertIn("to match the folder", errors)

    def test_label_file_must_be_draft(self):
        path = self.write("labels/pari/example-northwind.json", reconciled(labelers=["pari"]))
        self.assertIn("must be 'draft'", " ".join(validate.validate_label_file(path, self.checker)))

    def test_claims_file_duplicate_ids(self):
        path = self.write("claims.json", [reconciled(), reconciled()])
        self.assertIn("duplicate id", " ".join(validate.validate_claims_file(path, self.checker)))

    def test_invalid_json_reported(self):
        path = self.tmp / "claims.json"
        path.write_text("[{", encoding="utf-8")
        self.assertIn("cannot read JSON", " ".join(validate.validate_claims_file(path, self.checker)))


if __name__ == "__main__":
    unittest.main()
