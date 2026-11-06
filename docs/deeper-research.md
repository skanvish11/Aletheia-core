# Step 4: deeper research for one scoped claim

Step 4 builds on the Step 3 backend at `8647540`. Step 3 already supplied support
and counterevidence searches, quick-to-deep escalation, two follow-ups, immutable
citations, saved results, refresh and progress. This increment makes the research
loop evidence-aware and preserves capacity for useful follow-ups.

## Behavior

- A deterministic gate checks the current evidence after each research round.
  Material conflict takes priority over retrieval gaps. Otherwise it distinguishes
  inadequate evidence quality/independence, scope mismatch and missing evidence.
  It uses the existing verdict policy; it adds no extra model calls.
- Follow-up planning receives up to twelve evidence summaries, alternating support,
  contradiction, context and irrelevant assessments. Each summary carries its URL,
  evidence ID, admissibility, scope match, origin/independence, duplicate group,
  a rationale prefix (600 characters) and up to two excerpt prefixes (600 characters
  each). The omitted-assessment count is explicit. This is bounded search-planning
  context, not new evidence or a replacement for full saved excerpts. All text stays
  inside the existing untrusted-data boundary. Previous verdicts never enter planning.
- The planner also sees used queries and remaining search, page, model and time
  capacity. Duplicate queries and blank follow-up gaps are rejected, with one repair
  allowed under the same budget. Semantic usefulness remains model-assisted.
- Quick research selects at most two pages in its initial round. Deep research
  selects at most four initially and two per follow-up, with at most two follow-ups.
  These are page-selection ceilings, not extra provider allowances: failed requests
  and retries still consume the existing global limits. Multiple support queries
  do not crowd out the first counterevidence query in page selection.
- Fresh search candidates precede up to two historical URL leads on refresh.
  Old sources that do not fit remain `not_selected`, never falsely `retrieval_failed`
  or deleted. Every page actually used as current evidence is freshly extracted.
- Quick research escalates to deep once when the initial evidence cannot settle
  the claim. Accumulated attempts and the original clock remain intact. No planner
  call is started for a follow-up when no search or extraction capacity remains.
- `research_gate` events explain continuation/stopping. `sources_deferred` events
  report pages omitted under selection limits; they do not imply retrieval failure.
  The result discloses that some candidates were deferred during research, even if
  a later round happens to retrieve them. Existing `followup_planned` events now
  include the round number; `budget_reached` identifies the follow-up ceiling.
- No useful new query gives a normal `completed` result, possibly unable to decide.
  A call, deadline or round limit gives `partial`, retaining validated evidence and
  disclosing incomplete coverage. Unresolved conflict cannot become True or Almost
  merely by collecting more supporting pages. The existing finalization reserve
  remains four model attempts and 45 seconds; unchecked prose is never published.
- Deep evidence counting checks every pair of documented origins and content hashes.
  A greedy first choice previously could hide a valid later pair. Shared or unknown
  origins and duplicate content still cannot count as two independent observations.

Prompt/application versions are `one-claim-v4` and `research-v4`. Result configuration
records the page and follow-up limits. Existing saved records remain readable;
no database schema migration is needed. Clients consuming the event-type enumeration
should accept the two additional progress events.

## Acceptance evidence

The tests use FastAPI lifespans, real provider adapters with synthetic HTTP responses,
and temporary SQLite files. They never call paid providers or load real dotenv files.

| Requirement | Automated check in `tests/test_deeper_research.py` |
| --- | --- |
| Narrow-scope evidence triggers one escalation and a useful follow-up that settles the claim | `test_followup_uses_scope_gap_and_new_evidence_to_finish` |
| Counterevidence gets page capacity even with two support queries | `test_counterevidence_gets_page_capacity_beside_a_long_support_list` |
| Refresh includes fresh candidates despite old baseline pages | `test_refresh_prioritizes_fresh_search_results_over_old_pages` |
| Conflict takes priority over unavailable pages; empty follow-up ends honestly | `test_conflict_takes_priority_over_retrieval_gap_and_can_stop_honestly` |
| New counterevidence blocks an otherwise sufficient supporting finding | `test_counterevidence_in_followup_prevents_true_even_with_more_support` |
| Large candidate lists preserve both follow-ups and finalization | `test_large_source_lists_leave_capacity_for_two_followups_and_finalization` |
| Exhausted extraction capacity prevents wasted planning calls | `test_no_followup_planning_when_no_pages_can_be_extracted` |
| Repeated queries fail after one repair without further searches | `test_repeated_followup_queries_are_repaired_once_then_fail_without_search` |
| Whitespace-only gaps are invalid | `test_blank_followup_gap_is_rejected` |
| Origin counting is invariant to evidence order | `test_distinct_origin_and_content_pair_is_independent_of_order` |
| Bounded planner context retains dissent among many supporting assessments | `test_bounded_planning_context_keeps_counterevidence_among_many_supporting_passages` |

Existing suites also cover ambiguity, provider failures, unsupported citations,
hard deadlines, finalization reserves, immutable saved reads and shared escalation
budgets. The sensitivity script adds two deliberate faults in disposable copies:
removing round page limits and allowing a retrieval gap to hide a conflict. Both
must make the corresponding acceptance test fail.

Run from this checkout:

```sh
uv sync --locked --dev
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest
uv run --locked python scripts/check_research_test_sensitivity.py
```

Observed local results: **281 tests passed** (including twelve Step 4 cases), Ruff
lint/format and `git diff --check` passed, and all eight deliberate faults were
detected. Execution used the locked dependencies on Python 3.15.2 with the existing
offline cache. A Python 3.12 setup attempt could not obtain the required wheel:
it was absent from the cache and the package host could not be resolved. The
configured Python 3.12/3.13 CI matrix has not been run for this increment. No
independent agent review, live provider call or human research-quality evaluation
was performed. This validation concerns local behavior, not remote CI or accuracy.

## Scope and remaining validation

One scoped assertion per request remains the V1 boundary. Compound inputs still
ask for clarification. Advanced origin detection, automatic resolution of conflicting
assessments and frontend integration are not added here. Sources remain model-assessed;
structural checks cannot prove semantic truth or genuine source independence.

This increment has offline acceptance coverage only. Live provider accuracy, latency
and human passage review remain separate evaluation work. Time/call ceilings are
unchanged from Step 2's measured starting profiles, and remain provisional for full
investigations. No claim of real-world research accuracy follows from these tests.
