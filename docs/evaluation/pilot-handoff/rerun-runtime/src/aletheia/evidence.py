"""Immutable snapshots and quotations reconstructed only from supplied span IDs."""

import hashlib
import re
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from aletheia.providers.tavily import valid_url
from aletheia.research_contracts import Evidence, Excerpt, Snapshot, Span
from aletheia.tasks import TaskValidationError


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def navigation_only(text: str) -> bool:
    text = re.sub(r"^\s*[+*\-\d.)\s]+", "", text.strip())
    return bool(re.fullmatch(r"\[[^\]]+\]\(#[^)]+\)", text)) or text.startswith("#")


def canonical_url(url: str) -> str:
    parts = urlsplit(valid_url(url))
    # Keep path, query order, tracking parameters and scheme: do not merge uncertain identities.
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))


def snapshot(*, url, title, published_date, retrieved_at, text) -> Snapshot:
    normalized = re.sub(r"[^\S\n]+", " ", text.replace("\r\n", "\n").replace("\r", "\n"))
    spans = []
    # Preserve markdown blocks and line boundaries; prose sentences retain exact offsets.
    for line in re.finditer(r"[^\n]+", normalized):
        value = line.group()
        if not value.strip():
            continue
        block = bool(re.match(r"\s*(?:[#>|*+-]|\d+[.)]\s)", value)) or "|" in value
        pieces = (
            [line.span()]
            if block
            else [
                (line.start() + m.start(), line.start() + m.end())
                for m in re.finditer(r"\S.*?(?:[.!?](?=\s+[A-Z]|$)|$)", value)
                if m.group().strip()
            ]
        )
        for start, end in pieces:
            spans.append(
                Span(
                    id=len(spans) + 1,
                    start=start,
                    end=end,
                    text=normalized[start:end],
                    kind="block" if block else "sentence",
                )
            )
    content_hash = digest(normalized)
    return Snapshot(
        id=str(uuid4()),
        url=url,
        canonical_url=canonical_url(url),
        title=title,
        published_date=published_date,
        retrieved_at=retrieved_at,
        original_text=text,
        normalized_text=normalized,
        content_hash=content_hash,
        spans=spans,
        duplicate_group=content_hash,
        limitations=[],
    )


def excerpts(source: Snapshot, ids: list[int], supplied_ids: set[int]) -> list[Excerpt]:
    if not ids or ids != sorted(set(ids)) or not set(ids) <= supplied_ids:
        raise TaskValidationError("citation_spans")
    spans = {s.id: s for s in source.spans}
    if not set(ids) <= spans.keys():
        raise TaskValidationError("citation_spans")
    groups = []
    for span_id in ids:
        if groups and groups[-1][-1] + 1 == span_id:
            groups[-1].append(span_id)
        else:
            groups.append([span_id])
    result = []
    for group in groups:
        start, end = spans[group[0]].start, spans[group[-1]].end
        text = source.normalized_text[start:end]
        result.append(
            Excerpt(span_ids=group, start=start, end=end, text=text, quote_hash=digest(text))
        )
    return result


def admit(assessment, source: Snapshot, supplied_ids: set[int]) -> Evidence:
    if assessment.citation.snapshot_id != source.id:
        raise TaskValidationError("citation_snapshot")
    quotes = excerpts(source, assessment.citation.span_ids, supplied_ids)
    if assessment.relation in {"supports", "contradicts"} and all(
        navigation_only(s.text) for s in source.spans if s.id in assessment.citation.span_ids
    ):
        raise TaskValidationError("citation_content")
    if assessment.provenance_span_ids:
        excerpts(source, assessment.provenance_span_ids, supplied_ids)
    if assessment.independence == "established" and not (
        assessment.origin and assessment.provenance_note and assessment.provenance_span_ids
    ):
        raise TaskValidationError("provenance")
    if assessment.credible_synthesis and not assessment.synthesis_coverage:
        raise TaskValidationError("synthesis_coverage")
    if (
        assessment.relation == "supports"
        and assessment.scope_match
        and any(flag.type == "narrow_scope" for flag in assessment.flags)
    ):
        raise TaskValidationError("scope_flag")
    # Scope-mismatched passages can still provide context and explain a qualification;
    # they must never count as direct support or contradiction.
    admissible = assessment.relation == "context" or (
        assessment.scope_match and assessment.relation in {"supports", "contradicts"}
    )
    return Evidence(
        id=str(uuid4()),
        assessment=assessment,
        excerpts=quotes,
        admissible=admissible,
        rejection_reason=None if admissible else "scope_mismatch_or_irrelevant",
    )
