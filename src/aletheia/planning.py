"""Only validated, non-repeated queries can reach search."""

from aletheia.research_contracts import SearchPlan


def query_key(text):
    return " ".join(text.casefold().split())


def validate_plan(plan, seen, initial):
    keys = [query_key(q.text) for q in plan.queries]
    if any(not key or key in seen for key in keys) or len(set(keys)) != len(keys):
        raise ValueError("Queries must be nonblank, distinct and new.")
    if initial and not {"support", "contradiction"} <= {q.purpose for q in plan.queries}:
        raise ValueError("Initial plan requires support and counterevidence searches.")
    if not initial and plan.queries and not plan.gap:
        raise ValueError("Follow-up needs a named evidence gap.")


async def plan_search(tasks, assertion, route, seen, gap=None):
    return await tasks.call(
        "plan",
        "Propose at most three precise search queries for a1. The initial plan MUST include "
        "both support and contradiction searches; look for primary records and corrections. "
        "Follow-up queries must address the named evidence gap and must not repeat previous "
        "queries. Return no queries if there is no useful new search. Never use prior verdicts.",
        {
            "assertion": assertion.model_dump(),
            "route": route,
            "gap": gap,
            "previous_queries": sorted(seen),
            "remaining_search_attempts": tasks.budget.search_attempts - tasks.budget.used["search"],
        },
        SearchPlan,
        lambda value: validate_plan(value, seen, gap is None),
    )
