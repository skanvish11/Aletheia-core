"""Execute approved queries and save extracted sources before model assessment."""

from aletheia.evidence import canonical_url, snapshot
from aletheia.providers.errors import ErrorCode, ProviderError
from aletheia.verification import assess


def refresh_sources(sources, evidence, cited_ids):
    """Recheck cited evidence, prioritizing direct support/contradiction over context."""
    cited = [e for e in evidence if e.admissible and e.id in cited_ids]
    relevant = {e.assessment.citation.snapshot_id for e in cited}
    direct = {
        e.assessment.citation.snapshot_id
        for e in cited
        if e.assessment.relation in {"supports", "contradicts"}
    }
    return sorted((s for s in sources if s.id in relevant), key=lambda s: s.id not in direct)[:2]


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
    for query in plan.queries:
        await tasks.emit(
            "search_started", {"query": query.text, "purpose": query.purpose}, stage="searching"
        )
        result = await search.search(query.text, budget=tasks.budget, max_results=5)
        await tasks.emit(
            "search_completed",
            {"query": query.text, "result_count": str(len(result.results))},
            stage="searching",
        )
        batches.append((query.purpose, sorted(result.results, key=lambda hit: -hit.score)))
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
    # Cited old evidence gets reserved recheck slots, outside the fresh-page ceiling
    # but still inside every shared attempt/deadline limit.
    candidates = [(s.url, s.title, s.published_date) for s in baseline_sources[:2]]
    for index in range(5):
        for batch in ordered:
            if index < len(batch):
                hit = batch[index]
                candidates.append((hit.url, hit.title[:2000], hit.published_date))
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
    for url, title, published in selected:
        result = await search.extract([url], budget=tasks.budget)
        page = result.pages[0]
        if page.error or not page.content:
            await tasks.emit(
                "source_rejected",
                {"url": url, "reason": page.error or "empty_content"},
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
            source.limitations.append("Only the first bounded set of source spans was assessed.")
        duplicate = any(s.content_hash == source.content_hash for s in sources)
        await storage.save_records(run_id, "snapshot", [source])
        sources.append(source)
        await tasks.emit(
            "source_extracted",
            {"snapshot_id": source.id, "url": url, "duplicate": str(duplicate).lower()},
            stage="extracting",
        )
        if duplicate:
            continue
        await tasks.emit("stage_started", {"stage": "verifying"}, stage="verifying")
        checked, gap = await assess(tasks, assertion, source)
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
