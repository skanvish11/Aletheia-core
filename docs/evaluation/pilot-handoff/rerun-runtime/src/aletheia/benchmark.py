"""Versioned candidate datasets and failure-inclusive benchmark diagnostics."""

import hashlib
import json
import math
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from aletheia.contracts import InvestigationRequest
from aletheia.evaluation import EvaluationCase, EvaluationRecord, score, summarize

CLASSES = ("true", "false", "almost", "insufficient_evidence", "conflicting_evidence")
DOMAINS = ("science", "health", "technology", "economics", "history", "public_policy")


class Provenance(EvaluationRecord):
    method: Literal["original_ai_candidate", "published_dataset", "human_authored"]
    source_id: str
    source_url: str | None = None
    native_label: str | None = None
    evidence_status: Literal["unverified_leads", "imported_evidence", "human_verified"]
    # Do not confuse candidate creation date with factual verification date.
    last_verified: str | None = None

    @model_validator(mode="after")
    def valid_verification_date(self):
        if self.last_verified is not None:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", self.last_verified):
                raise ValueError("Verification date must use YYYY-MM-DD")
            date.fromisoformat(self.last_verified)
        return self


class BenchmarkCase(EvaluationCase):
    schema_version: Literal["1.0"] = "1.0"
    split: Literal["development", "reserved"]
    domain: Literal["science", "health", "technology", "economics", "history", "public_policy"]
    difficulty: Literal["easy", "medium", "hard"]
    family_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,100}$")
    provenance: Provenance
    evidence_passages: list[str] = Field(default_factory=list)
    pilot: bool = False

    @model_validator(mode="after")
    def reviewed_evidence(self):
        if self.status != "proposed" and (
            self.provenance.evidence_status != "human_verified"
            or not self.provenance.last_verified
            or not self.evidence_passages
            or any(len(p.strip()) < 10 for p in self.evidence_passages)
            or len({name.strip().casefold() for name in self.labelers if name.strip()}) < 2
        ):
            raise ValueError("Reviewed cases require dated, human-verified evidence passages")
        if self.pilot and self.split != "development":
            raise ValueError("Pilot cases must be development cases")
        return self


def normalized_claim(claim):
    return " ".join(re.findall(r"\w+", claim.casefold()))


def load_benchmark(path):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("A benchmark must be a nonempty array")
    cases = [BenchmarkCase.model_validate(c) for c in raw]
    for keys in (
        [c.id for c in cases],
        [normalized_claim(c.claim) for c in cases],
        [InvestigationRequest.model_validate(c.request()).request_key() for c in cases],
    ):
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate ID, normalized claim, or backend request")
    families = {}
    for case in cases:
        if families.setdefault(case.family_id, case.split) != case.split:
            raise ValueError("A claim family crosses development/reserved splits")
    return cases


def category(decision):
    if not decision:
        return "no_decision"
    return decision.get("verdict") or decision.get("unable_to_decide_reason") or "no_decision"


def benchmark_row(case, artifact):
    row = score(case, artifact)
    investigation = artifact.get("investigation") or {}
    row.update(
        expected=category(case.expected.model_dump()),
        predicted=category(investigation.get("result"))
        if investigation.get("status") == "completed"
        else "no_decision",
        domain=case.domain,
        difficulty=case.difficulty,
        split=case.split,
        family_id=case.family_id,
        elapsed_seconds=artifact.get("elapsed_seconds"),
        network_attempts=len(artifact["network_attempts"])
        if "network_attempts" in artifact
        else None,
        usage_observed={"prompt_tokens": 0, "completion_tokens": 0},
        usage_records=0,
    )
    # task_finished is one model attempt; don't also add provider diagnostics.
    for event in artifact.get("events", []):
        payload = event.get("payload", {})
        if event.get("type") == "task_finished":
            values = [payload.get(k) for k in row["usage_observed"]]
            if all(str(v).isdigit() for v in values):
                row["usage_records"] += 1
                for key in row["usage_observed"]:
                    row["usage_observed"][key] += int(payload[key])
    return row


def ratio(n, d):
    return n / d if d else None


def wilson(successes, total):
    if not total:
        return None
    z = 1.959963984540054
    p = successes / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return [max(0, center - half), min(1, center + half)]


def diagnostics(rows):
    n = len(rows)
    matrix = {k: dict(Counter(r["predicted"] for r in rows if r["expected"] == k)) for k in CLASSES}
    per_class = {}
    for k in CLASSES:
        support = sum(r["expected"] == k for r in rows)
        predicted = sum(r["predicted"] == k for r in rows)
        tp = sum(r["expected"] == k and r["predicted"] == k for r in rows)
        per_class[k] = {
            "support": support,
            "precision": ratio(tp, predicted),
            "recall": ratio(tp, support),
            "f1": ratio(2 * tp, support + predicted),
        }
    represented = [v["f1"] for v in per_class.values() if v["support"]]
    durations = sorted(r["elapsed_seconds"] for r in rows if r.get("elapsed_seconds") is not None)
    decided = [r for r in rows if r["predicted"] in ("true", "false", "almost")]
    abstentions = [r for r in rows if r["predicted"] in CLASSES[3:]]
    valid_abstentions = sum(r["expected"] == r["predicted"] for r in abstentions)
    matches = sum(r["decision_label_match"] for r in rows)
    return {
        "count": n,
        "decision_label_agreement": ratio(matches, n),
        "label_agreement_wilson95": wilson(matches, n),
        "interval_note": "Descriptive binomial interval; assumes independent claims. "
        "Not uncertainty about human truth or a population traffic estimate.",
        "confusion_matrix": matrix,
        "per_class": per_class,
        "macro_f1_represented_classes": sum(represented) / len(represented)
        if represented
        else None,
        "completion_rate": ratio(sum(r["status"] == "completed" for r in rows), n),
        "decisive_coverage": ratio(len(decided), n),
        "selective_label_accuracy": ratio(
            sum(r["decision_label_match"] for r in decided), len(decided)
        ),
        "abstention_precision_exact_reason": ratio(valid_abstentions, len(abstentions)),
        "abstention_recall_exact_reason": ratio(
            valid_abstentions, sum(r["expected"] in CLASSES[3:] for r in rows)
        ),
        "unnecessary_abstention_rate": ratio(
            sum(r["expected"] in CLASSES[:3] for r in abstentions),
            sum(r["expected"] in CLASSES[:3] for r in rows),
        ),
        "latency_seconds": {
            "observed": len(durations),
            "p50": durations[math.ceil(0.5 * len(durations)) - 1] if durations else None,
            "p95": durations[math.ceil(0.95 * len(durations)) - 1] if durations else None,
        },
        "network_attempts_observed": sum(r["network_attempts"] or 0 for r in rows),
        "network_attempts_missing_cases": sum(r["network_attempts"] is None for r in rows),
        "observed_tokens": {
            k: sum(r["usage_observed"][k] for r in rows)
            for k in ("prompt_tokens", "completion_tokens")
        },
        "usage_records": sum(r["usage_records"] for r in rows),
        "usage_note": (
            "Observed model usage only; missing reports and interrupted attempts are unknown."
        ),
        "billed_cost": None,
        "cost_per_correct_result": None,
        "citation_support_precision": None,
        "citation_coverage": None,
        "citation_review": "pending_human_review",
    }


def report(rows, planned):
    return {
        **summarize(rows, planned),
        "diagnostics": diagnostics(rows),
        "by_split": {
            s: diagnostics([r for r in rows if r["split"] == s])
            for s in sorted({r["split"] for r in rows})
        },
        "by_domain": {
            s: diagnostics([r for r in rows if r["domain"] == s])
            for s in sorted({r["domain"] for r in rows})
        },
        "by_difficulty": {
            s: diagnostics([r for r in rows if r["difficulty"] == s])
            for s in sorted({r["difficulty"] for r in rows})
        },
        "reviewed_only": diagnostics([r for r in rows if r["label_status"] != "proposed"]),
    }


def code_hash(root):
    """Only implementation files; never configuration files or evaluation labels."""
    paths = sorted(
        [
            *root.joinpath("src").rglob("*.py"),
            *root.joinpath("scripts").glob("*.py"),
            root / "uv.lock",
        ]
    )
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()
