"""Rebuild this published-label claim pack from the checksummed FEVER development file."""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
SOURCE_SHA256 = "e89865bfe1b4dd054e03dd57d7241a6fde24862905f31117cf0cd719f7c78df7"
SOURCE_URL = "https://zenodo.org/records/4925954/files/shared_task_dev.jsonl?download=1"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="Downloaded FEVER shared_task_dev.jsonl")
    args = parser.parse_args()
    raw = args.source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("FEVER source checksum differs")
    ids = [int(s) for s in (ROOT / "selected-ids.txt").read_text().split()]
    if len(ids) != 100 or len(set(ids)) != 100:
        raise ValueError("Expected exactly 100 unique IDs")
    originals = {r["id"]: r for r in map(json.loads, raw.splitlines()) if r["id"] in ids}
    if set(originals) != set(ids):
        raise ValueError("A selected ID is absent from the source")
    cases = []
    for index, id in enumerate(ids, 1):
        original = originals[id]
        if original["label"] != "SUPPORTS" or original["verifiable"] != "VERIFIABLE":
            raise ValueError(f"{id} lacks a verifiable SUPPORTS annotation")
        evidence = original["evidence"]
        pointers = sorted({(item[2], item[3]) for group in evidence for item in group
                           if len(item) == 4 and isinstance(item[2], str)
                           and isinstance(item[3], int) and item[3] >= 0})
        if not pointers:
            raise ValueError(f"{id} has no evidence sentence pointer")
        cases.append({
            "id": f"fever-{id}",
            "number": index,
            "claim": original["claim"],
            "context": {},
            "published_label": "SUPPORTS",
            "expected_verdict": "true",
            "label_status": "published_human_annotation; local_review_pending",
            "research_method": "direct_fact_or_comparison_pending_scope_review",
            "evidence_sentence_pointers": [
                {"page": page, "sentence": sentence,
                 "article_url": "https://en.wikipedia.org/wiki/" + quote(page, safe="_()")}
                for page, sentence in pointers
            ],
            "original_evidence_sets": evidence,
            "source_record_id": id,
            "source_dataset": "FEVER v1 shared task development",
            "reference_corpus": "English Wikipedia, June 2017",
            "current_web_verified_at": None,
            "local_labelers": [],
        })
    if len({c["claim"].casefold().strip() for c in cases}) != 100:
        raise ValueError("Duplicate claims")
    (ROOT / "claims.json").write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n")
    lines = ["# One hundred historically supported claims", "",
             "All claims below carry a FEVER SUPPORTS annotation against its June 2017 Wikipedia corpus. They are not locally reviewed or verified against today's web. Evidence sentence references are in `claims.json`.", ""]
    for case in cases:
        page = case["evidence_sentence_pointers"][0]["article_url"]
        lines.append(f"{case['number']}. {case['claim']}  ([FEVER {case['source_record_id']}]({page}))")
    (ROOT / "claims.md").write_text("\n".join(lines) + "\n")
    manifest = {
        "source": SOURCE_URL,
        "source_sha256": SOURCE_SHA256,
        "count": len(cases),
        "published_label_counts": {"SUPPORTS": 100},
        "reference_corpus": "English Wikipedia, June 2017",
        "current_web_verified_count": 0,
        "local_reviewed_count": 0,
        "backend_runs": 0,
        "claim_text_preserved": True,
        "claims_sha256": hashlib.sha256((ROOT / "claims.json").read_bytes()).hexdigest(),
        "license": "https://fever.ai/download/fever/license.html",
        "attribution": "Thorne, Vlachos, Christodoulopoulos, Mittal (2018), FEVER: a Large-scale Dataset for Fact Extraction and VERification",
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Wrote {len(cases)} source-labeled True claims")


if __name__ == "__main__":
    main()
