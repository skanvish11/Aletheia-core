"""Preserve the submitted claim and distinguish method support from missing scope."""

import re

from aletheia.task_contracts import ClaimPlan
from aletheia.tasks import TaskValidationError


def validate_claim(plan, original=None):
    if plan.clarification_reason == "factual_uncertainty":
        raise TaskValidationError("factual_uncertainty")
    if plan.questions and (plan.assertions or plan.clarification_reason != "missing_scope"):
        raise TaskValidationError("clarification_shape")
    if not plan.questions and plan.clarification_reason is not None:
        raise TaskValidationError("clear_claim_reason")
    if any(not q.strip() for q in plan.questions) or any(
        not a.text.strip() for a in plan.assertions
    ):
        raise TaskValidationError("blank_claim")
    if not plan.questions and len(plan.assertions) != 1:
        raise TaskValidationError("claim_shape")
    analysis = getattr(plan, "analysis", None)
    if analysis is not None:
        if bool(plan.questions) != (analysis.scope == "missing"):
            raise TaskValidationError("phase_one_scope")
        if original is not None:
            if any(c.text not in original for c in analysis.components):
                raise TaskValidationError("component_wording")
            # Dates and quantities in descriptive modifiers cannot disappear during parsing.
            numbers = set(re.findall(r"\b\d+(?:[.,]\d+)*\b", original))
            retained = set(
                re.findall(r"\b\d+(?:[.,]\d+)*\b", " ".join(c.text for c in analysis.components))
            )
            if not numbers <= retained:
                raise TaskValidationError("component_wording")
            if plan.assertions and plan.assertions[0].text != original:
                raise TaskValidationError("component_wording")


async def interpret(tasks, investigation):
    plan = await tasks.call(
        "interpret",
        "Preserve the submitted claim EXACTLY, including all descriptive modifiers, dates, "
        "negation and quantities. Do not correct from memory or decide truth. Return separate "
        "analysis fields for primary_type, scope, required_method and supported. Direct facts "
        "use record_lookup; direct comparisons use record_comparison. Other types use the "
        "corresponding unsupported method: causal, prediction, counterfactual, "
        "scientific_inference, interpretive or mixed. Topics are metadata, not methods. "
        "An unknown answer or unavailable record is not missing scope. A scientific existence "
        "hypothesis may require inference; a general existence assertion does not need an "
        "invented region or habitat. Do not route by expected truth or search success. "
        "Unsupported claims retain one assertion and all components, with questions=[] when "
        "scope is complete; never disguise a method limitation as a clarification. Mixed "
        "methods or independent propositions require mixed, never silently drop a part. "
        "Only genuinely missing essential scope permits questions, assertions=[], "
        "clarification_reason=missing_scope. Identify what the user must supply. Resolve "
        "relative dates only from supplied absolute context. For complete scope use null "
        "clarification_reason. Components must be exact substrings of the original claim, "
        "with c1..c8 IDs, subject, predicate, timeframe, location_or_population, and essential "
        "or modifier role. Separate date modifiers from the main proposition. Components "
        "must collectively retain EVERY material detail. Comparison fields specify both "
        "operands, metric, operator, units, period, population, definition and whether the "
        "claim is an exhaustive superlative. Use explicit 'not applicable' for fields that "
        "do not constrain the comparison; never invent an unspecified period or definition. "
        "For superlatives preserve the full comparison set as right; a counterexample can "
        "refute it, but a pair alone cannot prove it. Use direct_record assertion kind for "
        "supported claims. Research depth changes effort only, never the evidence standard.",
        {"claim": investigation.claim, "context": investigation.context},
        ClaimPlan,
        lambda value: validate_claim(value, investigation.claim),
    )
    if not plan.analysis.supported or plan.questions:
        reviewed = await tasks.call(
            "review_route",
            "Review the proposed scope and method classification against the ORIGINAL claim. "
            "Do not decide truth or silently correct wording. Missing scope must materially "
            "change the proposition. Unknown truth and unsupported inference are not missing "
            "scope; do not invent regions for a general existence claim. Preserve all material "
            "components and exact original assertion wording. Return the complete corrected "
            "plan, or the same plan if justified. Explain any changed "
            "classification in analysis.reason. "
            "No external evidence or expected answer is available.",
            {
                "claim": investigation.claim,
                "context": investigation.context,
                "proposed_plan": plan.model_dump(),
            },
            ClaimPlan,
            lambda value: validate_claim(value, investigation.claim),
        )
        if reviewed.analysis != plan.analysis:
            await tasks.emit(
                "route_revised",
                {
                    "previous_method": plan.analysis.required_method,
                    "method": reviewed.analysis.required_method,
                    "previous_scope": plan.analysis.scope,
                    "scope": reviewed.analysis.scope,
                    "reason": reviewed.analysis.reason,
                },
            )
        plan = reviewed
    if plan.assertions:
        plan.assertions[0] = plan.assertions[0].model_copy(
            update={
                "text": investigation.claim,
                "analysis": plan.analysis,
                "kind": "direct_record" if plan.analysis.supported else plan.assertions[0].kind,
            }
        )
    return plan


def route(assertion):
    deep = (
        assertion.recommended_route == "deep"
        or assertion.consequential
        or (not assertion.analysis and assertion.kind != "direct_record")
    )
    return (
        ("deep", "Additional research capacity requested; evidence requirements are unchanged.")
        if deep
        else ("quick", "A precise direct record may settle the claim.")
    )
