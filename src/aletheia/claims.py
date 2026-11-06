"""One-assertion interpretation and conservative, one-way research routing."""

from aletheia.research_contracts import ClaimPlan


def validate_claim(plan):
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
        "For clear factual claims supply a1, explicit scope and characteristics. "
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
