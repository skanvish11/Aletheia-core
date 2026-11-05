"""Execute approved queries and save extracted sources before model assessment."""

from aletheia.evidence import canonical_url, snapshot
from aletheia.verification import assess


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
        batches.append(sorted(result.results, key=lambda hit: -hit.score))
    # Include a bounded set of old URLs for refresh, then alternate query result lists so
    # counterevidence gets selection opportunities rather than only support-search hits.
    candidates = [(s.url, s.title, s.published_date) for s in baseline_sources[:2]]
    for index in range(5):
        for batch in batches:
            if index < len(batch):
                hit = batch[index]
                candidates.append((hit.url, hit.title[:2000], hit.published_date))
    selected = []
    remaining = tasks.budget.extraction_attempts - tasks.budget.used["extract"]
    for url, title, published in candidates:
        key = canonical_url(url)
        if key in seen_urls:
            continue
        if len(selected) >= remaining:
            break
        seen_urls.add(key)
        selected.append((url, title, published))
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
            gaps.append("Some selected sources could not be retrieved.")
            continue
        if len(page.content) > 100_000:
            await tasks.emit(
                "source_rejected", {"url": url, "reason": "page_size_limit"}, stage="extracting"
            )
            gaps.append("A selected page exceeded the stored text limit.")
            continue
        source = snapshot(
            url=url,
            title=title,
            published_date=published,
            retrieved_at=result.retrieved_at,
            text=page.content,
        )
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
