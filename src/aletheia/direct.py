"""Deterministic direct-claim decisions over grounded component evidence."""

import operator
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from aletheia.phase_one_contracts import ComponentFinding
from aletheia.tasks import TaskValidationError

NUMBER = r"[+−-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[eE][+-]?\d+)?"


def decimal_value(text):
    if not re.fullmatch(NUMBER, text):
        raise ValueError("Not an exact decimal representation.")
    return Decimal(text.replace(",", "").replace("−", "-"))


def normalized(value):
    return " ".join(value.casefold().split())


def comparison_relation(spec, values):
    """Return None when a comparison cannot safely establish a relation."""
    if len(values) != 2 or {v.side for v in values} != {"left", "right"}:
        return None
    left = next(v for v in values if v.side == "left")
    right = next(v for v in values if v.side == "right")
    if not left.exact or not right.exact or left.kind != right.kind:
        return None
    if normalized(left.entity) != normalized(spec.left):
        return None
    if not spec.exhaustive and normalized(right.entity) != normalized(spec.right):
        return None
    for field in ("metric", "units", "period", "population", "definition"):
        expected = normalized(getattr(spec, field))
        if any(normalized(getattr(v, field)) != expected for v in values):
            return None
    try:
        if left.kind == "property":
            if spec.operator not in {"eq", "ne"}:
                return None
            a, b = normalized(left.value), normalized(right.value)
        elif left.kind == "date":
            a, b = date.fromisoformat(left.value), date.fromisoformat(right.value)
        else:
            a, b = decimal_value(left.value), decimal_value(right.value)
            if not a.is_finite() or not b.is_finite():
                return None
    except (ValueError, InvalidOperation):
        return None
    result = getattr(operator, spec.operator)(a, b)
    # Pairwise support cannot establish an exhaustive superlative.
    if spec.exhaustive and result:
        return None
    return "supports" if result else "contradicts"


def validate_component_assessment(assessment, assertion, source, supplied):
    from aletheia.evidence import excerpts

    components = {c.id: c for c in assertion.analysis.components}
    if assessment.component_id not in components:
        raise TaskValidationError("component_reference")
    component = components[assessment.component_id]
    quoted = "\n".join(e.text for e in excerpts(source, assessment.citation.span_ids, supplied))
    if len({v.side for v in assessment.values}) != len(assessment.values):
        raise TaskValidationError("comparison_values")
    for value in assessment.values:
        if value.source_text not in quoted:
            raise TaskValidationError("comparison_values")
        # Do not accept an invented number inside a genuine but unrelated quote.
        if value.kind == "number":
            try:
                extracted = decimal_value(value.value)
                tokens = re.findall(
                    r"(?<![\w.,+−-])" + NUMBER + r"(?![\w,]|\.\d)", value.source_text
                )
                if not any(decimal_value(token) == extracted for token in tokens):
                    raise ValueError("No matching numeric token.")
            except (ValueError, InvalidOperation):
                raise TaskValidationError("comparison_values") from None
        if value.kind in {"date", "property"} and value.value not in value.source_text:
            # Non-ISO dates remain available as contextual evidence; no implicit conversion.
            raise TaskValidationError("comparison_values")
    if component.comparison:
        relation = comparison_relation(component.comparison, assessment.values)
        if assessment.relation in {"supports", "contradicts"} and (
            relation is None or assessment.relation != relation
        ):
            raise TaskValidationError("comparison_relation")
    elif assessment.values:
        raise TaskValidationError("comparison_values")


def component_findings(assertion, evidence, sources, sufficient):
    findings = []
    for component in assertion.analysis.components:
        items = [e for e in evidence if e.assessment.component_id == component.id]
        support = [e for e in items if e.assessment.relation == "supports"]
        contra = [e for e in items if e.assessment.relation == "contradicts"]
        outcome = "not_established"
        if component.comparison:
            # Operands can come from different documents. Each value requires its own
            # adequate evidence; unrelated values cannot borrow another source's authority.
            grounded = []
            for item in items:
                if not item.assessment.scope_match:
                    continue
                for value in item.assessment.values:
                    matching = [
                        e
                        for e in items
                        if e.assessment.scope_match
                        and any(
                            v.model_dump(exclude={"source_text"})
                            == value.model_dump(exclude={"source_text"})
                            for v in e.assessment.values
                        )
                    ]
                    if sufficient(matching, "quick", sources):
                        grounded.append(value)
            relations = {
                comparison_relation(component.comparison, [left, right])
                for left in grounded
                if left.side == "left"
                for right in grounded
                if right.side == "right"
            } - {None}
            if relations == {"supports", "contradicts"}:
                outcome = "conflicting"
            elif relations == {"supports"}:
                outcome = "supported"
            elif relations == {"contradicts"}:
                outcome = "contradicted"
        elif support and contra:
            outcome = "conflicting"
        elif sufficient(support, "quick", sources):
            outcome = "supported"
        elif sufficient(contra, "quick", sources):
            outcome = "contradicted"
        findings.append(
            ComponentFinding(
                component_id=component.id, outcome=outcome, evidence_ids=[e.id for e in items]
            )
        )
    return findings
