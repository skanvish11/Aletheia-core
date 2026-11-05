"""Bounded one-claim pipeline, with durable progress and explicit terminal outcomes."""

from dataclasses import asdict

from aletheia.budgets import RunBudget
from aletheia.claims import interpret, route
from aletheia.comparison import compare
from aletheia.planning import plan_search, query_key
from aletheia.providers.errors import ErrorCode, ProviderError
from aletheia.research import gather
from aletheia.research_contracts import InvestigationResult, Snapshot
from aletheia.tasks import PROMPT_VERSION, InvalidTask, Tasks
from aletheia.verdicts import finding, synthesize

APPLICATION_VERSION = "research-v2"


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
            baseline_sources = (
                await self.storage.records(investigation.parent_id, "snapshot", Snapshot)
                if investigation.parent_id
                else []
            )
            gap = None
            for round_index in range(3):
                await emit("stage_started", {"stage": "planning"}, stage="planning")
                search_plan = await plan_search(tasks, assertion, assigned_route, seen, gap)
                if not search_plan.queries:
                    break
                if round_index:
                    await emit("followup_planned", {"gap": gap})
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
                )
                computed, _ = finding(assertion, assigned_route, evidence, sources)
                if computed.verdict in {"true", "false"}:
                    stop_reason = "evidence_sufficient"
                    break
                if assigned_route == "quick":
                    assigned_route = "deep"
                    budget.escalate()
                    await emit(
                        "route_escalated",
                        {"reason": "Direct evidence did not settle the claim."},
                        route="deep",
                    )
                gap = gap or (
                    "Resolve supporting and contradicting evidence."
                    if computed.unable_to_decide_reason == "conflicting_evidence"
                    else "Find direct records or independent evidence for the exact scope."
                )
            else:
                stop_reason, partial = "budget_exhausted", True
                limitations.append("The follow-up round limit was reached.")
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
        if any(e.type == "source_rejected" for e in await self.storage.events(investigation.id)):
            limitations.append("Some selected pages were unavailable or exceeded the text limit.")
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
                "duration_limit_seconds": budget.deadline - budget.started,
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
