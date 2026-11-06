"""One-assertion interpretation and conservative, one-way research routing."""

from aletheia.task_contracts import ClaimPlan
from aletheia.tasks import TaskValidationError


def validate_claim(plan):
    if plan.clarification_reason == "factual_uncertainty":
        raise TaskValidationError("factual_uncertainty")
    if plan.questions and (plan.assertions or plan.clarification_reason is None):
        raise ValueError("Clarification requires a scope reason and no assertions.")
    if not plan.questions and plan.clarification_reason is not None:
        raise ValueError("A clear claim must not have a clarification reason.")
    if any(not q.strip() for q in plan.questions) or any(
        not a.text.strip() for a in plan.assertions
    ):
        raise ValueError("Claim and clarification text must not be blank.")
    if not plan.questions and len(plan.assertions) != 1:
        raise ValueError("A clear claim requires one assertion.")


async def interpret(tasks, investigation):
    return await tasks.call(
        "interpret",
        "Interpret exactly one factual assertion without changing its meaning. For compound "
        "claims, unresolved relative dates, ambiguous scope, predictions or value judgments, "
        "return clarification questions and no assertions. Resolve relative dates only from "
        "explicit user-supplied absolute timeframe context; never silently use today's date. "
        "For clear factual claims supply a1, explicit scope and characteristics, with "
        "questions=[] and clarification_reason=null. False premises, unknown answers, "
        "contested evidence and uncertainty about a named person's nationality or an "
        "event's equipment are research questions, NOT missing user scope. Preserve those "
        "details in the assertion; do not correct them from memory. Never ask the user "
        "whether the claim is true, what the evidence establishes or which fact is correct. "
        "Clarification must identify missing scope the user can supply (which entity, "
        "period, place or definition), separate independently asserted propositions, or "
        "a non-factual request. Set the corresponding clarification_reason. A subject's "
        "descriptive modifier does not by itself make one proposition compound. "
        "A direct record is a precise date/quantity/event lookup. Consequential causal, medical, "
        "legal or financial interpretations require deep research; a publication-date lookup "
        "does not become consequential merely because it concerns a medical paper.",
        {"claim": investigation.claim, "context": investigation.context},
        ClaimPlan,
        validate_claim,
    )


def route(assertion):
    deep = (
        assertion.recommended_route == "deep"
        or assertion.consequential
        or assertion.kind != "direct_record"
    )
    return (
        ("deep", "Claim meaning requires deeper evidence.")
        if deep
        else ("quick", "A precise direct record may settle the claim.")
    )
