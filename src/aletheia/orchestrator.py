"""Bounded one-claim pipeline, with durable progress and explicit terminal outcomes."""

from dataclasses import asdict

from aletheia.budgets import RunBudget
from aletheia.claims import interpret, route
from aletheia.comparison import compare
from aletheia.planning import plan_search, query_key
from aletheia.providers.errors import ErrorCode, ProviderError
from aletheia.research import gather, refresh_sources
from aletheia.research_contracts import Evidence, InvestigationResult, Snapshot
from aletheia.research_gate import evaluate, planning_context
from aletheia.tasks import PROMPT_VERSION, InvalidTask, Tasks
from aletheia.verdicts import finding, synthesize

APPLICATION_VERSION = "research-v4.3"
MAX_FOLLOWUP_ROUNDS = 2


class Pipeline:
    def __init__(self, storage, model, search, model_name, budget_factory=RunBudget):
        self.storage, self.model, self.search = storage, model, search
        self.model_name, self.budget_factory = model_name, budget_factory

    async def run(self, investigation):
        budget = self.budget_factory()

        async def emit(event, payload, **kwargs):
            await self.storage.progress(investigation.id, event, payload, **kwargs)

        tasks = Tasks(self.model, budget, emit)
        sources, evidence, seen, seen_urls = [], [], set(), set()
        limitations = []
        plan = None
        assigned_route = "quick"
        stop_reason, partial = "no_useful_query", False
        round_index = 0
        try:
            await emit("stage_started", {"stage": "interpreting"}, stage="interpreting")
            plan = await interpret(tasks, investigation)
            if plan.questions:
                await self.storage.finish(
                    investigation.id, status="needs_clarification", questions=plan.questions
                )
                return
            assertion = plan.assertions[0]
            if assertion.kind in {"predictive", "value"}:
                await self.storage.finish(
                    investigation.id,
                    status="needs_clarification",
                    questions=[
                        "Please submit a factual claim checkable against existing evidence."
                    ],
                )
                return
            await emit("claim_interpreted", {"assertion_id": assertion.id})
            assigned_route, reason = route(assertion)
            if assigned_route == "deep":
                budget.escalate()
            await emit(
                "route_selected", {"route": assigned_route, "reason": reason}, route=assigned_route
            )
            parent = (
                await self.storage.get(investigation.parent_id) if investigation.parent_id else None
            )
            baseline_sources = (
                await self.storage.records(investigation.parent_id, "snapshot", Snapshot)
                if parent and parent.result
                else []
            )
            if parent and parent.result:
                baseline_sources = refresh_sources(
                    baseline_sources,
                    await self.storage.records(parent.id, "evidence", Evidence),
                    set(parent.result.finding.evidence_ids),
                )
            gap = None
            gap_reason = "missing_evidence"
            for round_index in range(MAX_FOLLOWUP_ROUNDS + 1):
                if round_index:
                    # Do not spend a planning call when its searches/pages cannot execute.
                    budget.check("tavily", "search", 1)
                    budget.check("tavily", "extract", 1)
                await emit("stage_started", {"stage": "planning"}, stage="planning")
                search_plan = await plan_search(
                    tasks,
                    assertion,
                    assigned_route,
                    seen,
                    gap,
                    planning_context(evidence, sources),
                )
                if not search_plan.queries:
                    await emit(
                        "research_gate",
                        {"action": "stop", "reason": "no_useful_query", "round": str(round_index)},
                    )
                    break
                if round_index:
                    # Announce a follow-up only once a nonempty plan exists and its
                    # next search, extraction and assessment still have capacity.
                    budget.check("tavily", "search", 1)
                    budget.check("tavily", "extract", 1)
                    budget.check("nebius", "model", 1)
                    await emit(
                        "research_gate",
                        {
                            "action": "followup",
                            "reason": gap_reason,
                            "gap": gap,
                            "round": str(round_index - 1),
                        },
                    )
                    await emit("followup_planned", {"gap": gap, "round": str(round_index)})
                seen.update(query_key(q.text) for q in search_plan.queries)
                gap = await gather(
                    tasks,
                    self.search,
                    self.storage,
                    investigation.id,
                    assertion,
                    search_plan,
                    sources,
                    evidence,
                    seen_urls,
                    baseline_sources if round_index == 0 else (),
                    page_limit=2 if assigned_route == "quick" or round_index else 4,
                )
                gate = evaluate(assertion, assigned_route, evidence, sources, gap)
                if gate.sufficient or round_index == MAX_FOLLOWUP_ROUNDS:
                    await emit(
                        "research_gate",
                        {
                            "action": "stop",
                            "reason": gate.reason if gate.sufficient else "followup_round_limit",
                            "gap": gate.gap or "",
                            "round": str(round_index),
                        },
                    )
                if gate.sufficient:
                    stop_reason = "evidence_sufficient"
                    break
                if assigned_route == "quick":
                    assigned_route = "deep"
                    budget.escalate()
                    await emit(
                        "route_escalated",
                        {"reason": gate.reason},
                        route="deep",
                    )
                gap = gate.gap
                gap_reason = gate.reason
            else:
                stop_reason, partial = "budget_exhausted", True
                limitations.append("The follow-up round limit was reached.")
                await emit("budget_reached", {"reason": "followup_round_limit"})
        except ProviderError as exc:
            if exc.code not in {ErrorCode.BUDGET, ErrorCode.DEADLINE}:
                await self.storage.finish(
                    investigation.id,
                    status="failed",
                    stop_reason="provider_failure",
                    error="A research provider could not complete the investigation.",
                )
                return
            if not plan or not plan.assertions:
                await self.storage.finish(
                    investigation.id,
                    status="failed",
                    stop_reason=exc.code.value,
                    error="The investigation limit was reached before interpretation completed.",
                )
                return
            stop_reason, partial = exc.code.value, True
            limitations.append("Research stopped at a time or call limit; coverage is incomplete.")
            await emit(
                "research_gate",
                {"action": "stop", "reason": stop_reason, "round": str(round_index)},
            )
            await emit("budget_reached", {"reason": stop_reason})
        except InvalidTask:
            await self.storage.finish(
                investigation.id,
                status="failed",
                stop_reason="provider_failure",
                error="Research output failed validation; no factual verdict was published.",
            )
            return

        budget.finalizing = True
        assertion = plan.assertions[0]
        computed, dropped = finding(assertion, assigned_route, evidence, sources)
        for evidence_id in dropped:
            await emit("qualification_flag_dropped", {"evidence_id": evidence_id})
        limitations.extend(note for s in sources for note in s.limitations)
        limitations.extend(note for e in evidence for note in e.assessment.limitations)
        events = await self.storage.events(investigation.id)
        if any(e.type == "source_rejected" for e in events):
            limitations.append("Some selected pages were unavailable or exceeded the text limit.")
        if any(e.type == "sources_deferred" for e in events):
            limitations.append(
                "Some search results were not extracted within per-round page limits."
            )
        explanation = []
        if budget.remaining_seconds() > 0:
            await emit("stage_started", {"stage": "synthesizing"}, stage="synthesizing")
            try:
                computed, explanation = await synthesize(
                    tasks, assertion, computed, evidence, assigned_route, sources
                )
            except ProviderError as exc:
                if exc.code not in {ErrorCode.BUDGET, ErrorCode.DEADLINE}:
                    await self.storage.finish(
                        investigation.id,
                        status="failed",
                        stop_reason="provider_failure",
                        error="A research provider could not finalize the investigation.",
                    )
                    return
                # The policy finding is already valid, but no unchecked generated prose is saved.
                partial, stop_reason = True, exc.code.value
                limitations.append(
                    "The explanation could not be finalized within the investigation limits."
                )
            except InvalidTask:
                await self.storage.finish(
                    investigation.id,
                    status="failed",
                    stop_reason="provider_failure",
                    error="Final explanation failed validation; no factual verdict was published.",
                )
                return
        else:
            partial, stop_reason = True, "deadline_exceeded"
            limitations.append("The hard deadline prevented a generated explanation.")
        limitations.extend(computed.limitations)
        result = InvestigationResult(
            assertion=assertion,
            scope_note=plan.scope_note,
            outcome=computed.outcome,
            verdict=computed.verdict,
            unable_to_decide_reason=computed.unable_to_decide_reason,
            almost_correction=computed.almost_correction,
            finding=computed,
            explanation=explanation,
            limitations=list(dict.fromkeys(limitations)),
            model=self.model_name,
            prompt_version=PROMPT_VERSION,
            application_version=APPLICATION_VERSION,
            configuration={
                "response_format": self.model.settings.nebius_response_format,
                "nebius_thinking": self.model.settings.nebius_thinking,
                "max_output_tokens": self.model.settings.max_output_tokens,
                "provider_max_retries": self.model.settings.max_retries,
                "provider_timeout_seconds": self.model.settings.timeout_seconds,
                "max_request_bytes": self.model.settings.max_request_bytes,
                "max_response_bytes": self.model.settings.max_response_bytes,
                "max_extracted_chars": self.search.settings.max_extracted_chars,
                "model_attempt_limit": budget.model_attempts,
                "search_attempt_limit": budget.search_attempts,
                "extraction_attempt_limit": budget.extraction_attempts,
                "finalization_reserve_seconds": budget.reserve_seconds,
                "finalization_reserve_model_attempts": budget.reserve_model_attempts,
                "duration_limit_seconds": budget.deadline - budget.started,
                "max_followup_rounds": MAX_FOLLOWUP_ROUNDS,
                "quick_initial_page_limit": 2,
                "deep_initial_page_limit": 4,
                "followup_page_limit": 2,
                "refresh_recheck_page_limit": 2,
            },
            budget_used=dict(budget.used),
            provider_attempts=[asdict(a) for a in budget.attempts],
            token_usage=tasks.tokens,
        )
        # Comparison happens only AFTER the new answer is formed. Old verdicts never enter prompts.
        investigation.route = assigned_route
        comparison = await compare(self.storage, investigation, result, sources, evidence)
        await self.storage.finish(
            investigation.id,
            status="partial" if partial else "completed",
            stop_reason=stop_reason,
            result=result,
            comparison=comparison,
        )
