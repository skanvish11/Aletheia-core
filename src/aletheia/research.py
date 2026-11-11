"""Execute approved queries and save extracted sources before model assessment."""

from aletheia.evidence import canonical_url, snapshot
from aletheia.providers.errors import ErrorCode, ProviderError
from aletheia.tasks import InvalidTask
from aletheia.verification import assess


def refresh_sources(sources, evidence, cited_ids):
    """Recheck both cited sides before filling remaining slots with direct/context sources."""
    cited = [e for e in evidence if e.admissible and e.id in cited_ids]
    relevant = {e.assessment.citation.snapshot_id for e in cited}
    direct = {
        e.assessment.citation.snapshot_id
        for e in cited
        if e.assessment.relation in {"supports", "contradicts"}
    }
    chosen, chosen_ids = [], set()
    for relation in ("supports", "contradicts"):
        side = {
            e.assessment.citation.snapshot_id for e in cited if e.assessment.relation == relation
        }
        if chosen_ids & side:
            continue
        for candidate in sources:
            if candidate.id in side:
                chosen.append(candidate)
                chosen_ids.add(candidate.id)
                break
    remaining = sorted(
        (s for s in sources if s.id in relevant and s.id not in chosen_ids),
        key=lambda s: s.id not in direct,
    )
    return (chosen + remaining)[:2]


async def gather(
    tasks,
    search,
    storage,
    run_id,
    assertion,
    plan,
    sources,
    evidence,
    seen_urls,
    baseline_sources=(),
    *,
    page_limit=None,
):
    batches = []
    discovered_by = {}
    for query in plan.queries:
        query_id = tasks.budget.trace_id("q")
        await tasks.emit(
            "search_started",
            {"query": query.text, "purpose": query.purpose, "query_id": query_id},
            stage="searching",
        )
        try:
            with tasks.budget.tracing(query_id=query_id):
                result = await search.search(query.text, budget=tasks.budget, max_results=5)
        except ProviderError as exc:
            if not batches:
                raise
            # A retry may exhaust capacity even after a valid plan. Preserve completed searches.
            await tasks.emit("search_incomplete", {"reason": exc.code.value}, stage="searching")
            break
        await tasks.emit(
            "search_completed",
            {"query": query.text, "query_id": query_id, "result_count": str(len(result.results))},
            stage="searching",
        )
        batches.append((query.purpose, sorted(result.results, key=lambda hit: -hit.score)))
        for hit in result.results:
            discovered_by.setdefault(canonical_url(hit.url), []).append(query_id)
    # Alternate purposes before alternating result ranks. Two support queries must not
    # crowd the counterevidence query out of a two-page round.
    groups = [
        [hits for purpose, hits in batches if purpose == wanted]
        for wanted in ("support", "contradiction", "context")
    ]
    ordered = [
        group[index]
        for index in range(max((len(group) for group in groups), default=0))
        for group in groups
        if index < len(group)
    ]
    # Prefer current search metadata when a rechecked URL also appears in fresh hits.
    fresh_metadata = {}
    for batch in ordered:
        for hit in batch:
            fresh_metadata.setdefault(
                canonical_url(hit.url), (hit.url, hit.title[:2000], hit.published_date)
            )
    # Cited old evidence gets reserved recheck slots, outside the fresh-page ceiling
    # but still inside every shared attempt/deadline limit.
    candidates = [
        fresh_metadata.get(s.canonical_url, (s.url, s.title, s.published_date))
        for s in baseline_sources[:2]
    ]
    ranked_keys = seen_urls | {canonical_url(url) for url, _, _ in candidates}
    streams = [iter(batch) for batch in ordered]
    while True:
        added = False
        for stream in streams:
            for hit in stream:
                key = canonical_url(hit.url)
                if key in ranked_keys:
                    continue
                ranked_keys.add(key)
                candidates.append(fresh_metadata[key])
                added = True
                break
        if not added:
            break
    selected = []
    candidate_keys = set()
    remaining = tasks.budget.extraction_attempts - tasks.budget.used["extract"]
    if page_limit is not None:
        remaining = min(remaining, page_limit + len(baseline_sources[:2]))
    for url, title, published in candidates:
        key = canonical_url(url)
        if key in seen_urls or key in candidate_keys:
            continue
        candidate_keys.add(key)
        if len(selected) >= remaining:
            continue
        seen_urls.add(key)
        selected.append((url, title, published))
    deferred = len(candidate_keys) - len(selected)
    if deferred:
        await tasks.emit(
            "sources_deferred",
            {"count": str(deferred), "reason": "Per-round page or remaining extraction limit."},
            stage="extracting",
        )
    if not selected:
        return "No new extractable sources were found."
    gaps = []
    for slot, (url, title, published) in enumerate(selected, start=1):
        candidate_id = tasks.budget.trace_id("c")
        await tasks.emit(
            "source_selected",
            {
                "candidate_id": candidate_id,
                "url": url,
                "slot": str(slot),
                "query_ids": ",".join(discovered_by.get(canonical_url(url), [])),
                "selection_rule": "baseline_recheck"
                if any(s.canonical_url == canonical_url(url) for s in baseline_sources[:2])
                else "purpose_balanced_search_rank",
            },
            stage="extracting",
        )
        await tasks.emit("stage_started", {"stage": "extracting"}, stage="extracting")
        with tasks.budget.tracing(candidate_id=candidate_id):
            result = await search.extract([url], budget=tasks.budget)
        page = result.pages[0]
        if page.error or not page.content:
            await tasks.emit(
                "source_rejected",
                {"url": url, "candidate_id": candidate_id, "reason": page.error or "empty_content"},
                stage="extracting",
            )
            if page.error in {
                ErrorCode.BUDGET,
                ErrorCode.DEADLINE,
                ErrorCode.AUTHENTICATION,
                ErrorCode.QUOTA,
                ErrorCode.CONFIGURATION,
            }:
                raise ProviderError("tavily", ErrorCode(page.error))
            gaps.append("Some selected sources could not be retrieved.")
            continue
        source = snapshot(
            url=url,
            title=title,
            published_date=published,
            retrieved_at=result.retrieved_at,
            text=page.content,
        )
        source.limitations.extend(page.limitations)
        if len(source.spans) > 120 or sum(len(s.text) for s in source.spans) > 12000:
            source.limitations.append(
                "Only a relevant bounded selection of source spans was assessed."
            )
        duplicate = any(s.content_hash == source.content_hash for s in sources)
        await storage.save_records(run_id, "snapshot", [source])
        sources.append(source)
        await tasks.emit(
            "source_extracted",
            {
                "snapshot_id": source.id,
                "url": url,
                "candidate_id": candidate_id,
                "duplicate": str(duplicate).lower(),
            },
            stage="extracting",
        )
        if duplicate:
            continue
        await tasks.emit("stage_started", {"stage": "verifying"}, stage="verifying")
        try:
            checked, gap = await assess(tasks, assertion, source)
        except InvalidTask:
            await tasks.emit(
                "assessment_rejected",
                {
                    "snapshot_id": source.id,
                    "reason": "invalid_task_output",
                },
                stage="verifying",
            )
            gaps.append("A selected source assessment failed validation; coverage is incomplete.")
            continue
        await storage.save_records(run_id, "evidence", checked)
        evidence.extend(checked)
        for item in checked:
            await tasks.emit(
                "evidence_checked",
                {
                    "evidence_id": item.id,
                    "snapshot_id": source.id,
                    "admissible": str(item.admissible).lower(),
                    "relation": item.assessment.relation,
                },
                stage="verifying",
            )
        if gap:
            gaps.append(gap)
    return gaps[0] if gaps else None
