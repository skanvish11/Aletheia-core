"""Select relevant immutable spans across a document while retaining nearby context."""

import re
from collections import Counter

STOP = set(
    "the a an is was were in on of to and or for at by with from that this as it its".split()
)


def terms(text):
    return set(re.findall(r"[\w]+", text.casefold())) - STOP


def boilerplate(text):
    stripped = text.strip()
    return bool(
        re.fullmatch(r"(?:[-*]\s*)?\[[^\]]+\]\([^\n]+\)", stripped)
        or normalized_navigation(stripped)
    )


def normalized_navigation(text):
    # Markdown formatting alone does not make a heading navigation.
    label = re.sub(r"^#{1,6}\s+", "", text).rstrip("#").strip()
    return label.casefold() in {
        "skip to content",
        "navigation",
        "contents",
        "menu",
        "log in",
        "sign in",
        "privacy policy",
        "cookie policy",
        "accept cookies",
        "jump to content",
    }


def select_passages(assertion, source, *, max_chars=12000, max_spans=120):
    candidates = [s for s in source.spans if not boilerplate(s.text)]
    if not candidates:
        return []
    query = terms(assertion.text)
    # Document-frequency weighting reduces repeated menu/entity mentions.
    frequencies = Counter(t for span in candidates for t in terms(span.text))
    ranked = sorted(
        candidates, key=lambda s: (-sum(1 / frequencies[t] for t in terms(s.text) & query), s.id)
    )
    by_id = {s.id: s for s in candidates}
    selected, size = {}, 0
    for anchor in ranked:
        if anchor.id in selected or len(anchor.text) > max_chars:
            continue
        # Reserve space for the anchor before adding context, preserving original IDs.
        for span_id in (anchor.id, anchor.id - 1, anchor.id + 1):
            span = by_id.get(span_id)
            if span is None or span_id in selected:
                continue
            if size + len(span.text) <= max_chars and len(selected) < max_spans:
                selected[span_id] = span
                size += len(span.text)
    return [selected[i] for i in sorted(selected)]
