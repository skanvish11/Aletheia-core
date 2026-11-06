"""Only validated, non-repeated queries can reach search."""

from aletheia.research_contracts import SearchPlan
from aletheia.tasks import TaskValidationError


def query_key(text):
    return " ".join(text.casefold().split())


def validate_plan(plan, seen, initial):
    keys = [query_key(q.text) for q in plan.queries]
    if any(not key or key in seen for key in keys) or len(set(keys)) != len(keys):
        raise TaskValidationError("query_identity")
    if (
        initial
        and plan.queries
        and not {"support", "contradiction"} <= {q.purpose for q in plan.queries}
    ):
        raise TaskValidationError("query_coverage")
    if not initial and plan.queries and (not plan.gap or not plan.gap.strip()):
        raise TaskValidationError("query_gap")


async def plan_search(tasks, assertion, route, seen, gap=None, evidence_context=None):
    return await tasks.call(
        "plan",
        "Propose at most three precise search queries for a1. A nonempty initial plan MUST include "
        "both support and contradiction searches; look for primary records and corrections. "
        "Follow-up queries must address the named evidence gap and must not repeat previous "
        "queries. Use the supplied evidence summaries to target missing scope, original sources "
        "and disagreements. Summaries may be truncated; rejected evidence contributes metadata "
        "only. These are search leads, not new evidence. Stay within remaining search and "
        "extraction attempts. "
        "Return no queries if there is no useful new search. Never use prior verdicts.",
        {
            "assertion": assertion.model_dump(),
            "route": route,
            "gap": gap,
            "previous_queries": sorted(seen),
            "remaining_search_attempts": tasks.budget.search_attempts - tasks.budget.used["search"],
            "remaining_extraction_attempts": tasks.budget.extraction_attempts
            - tasks.budget.used["extract"],
            "remaining_research_model_attempts": tasks.budget.model_attempts
            - tasks.budget.reserve_model_attempts
            - tasks.budget.used["model"],
            "remaining_research_seconds": tasks.budget.remaining_seconds(),
            "evidence_context": evidence_context or {"summaries": [], "omitted_assessments": 0},
        },
        SearchPlan,
        lambda value: validate_plan(value, seen, gap is None),
    )
