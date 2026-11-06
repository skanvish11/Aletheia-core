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
  contradiction, context and irrelevant assessments. Within each relation, admitted
  evidence precedes rejected metadata so rejection floods cannot hide a real conflict.
  Each summary carries its URL,
  evidence ID, admissibility, scope match, independence and duplicate group.
  Only admissible evidence includes origin, a rationale prefix (600 characters)
  and up to two excerpt prefixes (600 characters each). Rejected evidence contributes
  metadata only; rejected rationale, origin text and passages are excluded.
  The omitted-assessment count is explicit. This is bounded search-planning
  context, not new evidence or a replacement for full saved excerpts. All text stays
  inside the existing untrusted-data boundary. Previous verdicts never enter planning.
- The planner also sees used queries and remaining search, page, model and time
  capacity. Duplicate queries and blank follow-up gaps are rejected, with one repair
  allowed under the same budget. Semantic usefulness remains model-assisted.
- Quick research selects at most two pages in its initial round. Deep research
  selects at most four initially and two per follow-up, with at most two follow-ups.
  These are page-selection ceilings, not extra provider allowances: failed requests
  and retries still consume the existing global limits. Multiple support queries
  do not crowd out the first counterevidence query in page selection. Each query's
  selection turn advances past already-seen or duplicate URLs to its next distinct
  candidate before moving to another query.
- Refresh reserves recheck slots for up to two sources cited by the saved result,
  prioritizing supporting/contradicting evidence over context and excluding rejected
  or uncited snapshots. When both sides were cited, reserve a source covering each
  side before filling remaining slots. Current search metadata replaces old metadata
  when the same URL is rediscovered. Rechecks precede fresh search candidates and sit outside
  the per-round fresh-page ceiling, but consume the same global attempt/time budgets.
  A quick refresh that cannot finish both sets reports `partial`, preserves validated
  findings, and still finalizes/computes comparison within its reserve. No budget
  increases or cached assessments are used. Old sources that do not fit remain
  `not_selected`, never falsely `retrieval_failed` or deleted.
- Quick research escalates to deep once when the initial evidence cannot settle
  the claim. Accumulated attempts and the original clock remain intact. No planner
  call is started for a follow-up when no search or extraction capacity remains.
- `research_gate` announces a follow-up only after a nonempty plan passes remaining
  search, extraction and assessment capacity checks, immediately before
  `followup_planned`. Empty plans and exhausted capacity emit a stop instead.
  `sources_deferred` events
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

Prompt/application versions are `one-claim-v4.2` and `research-v4.2`. Result configuration
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
| Refresh reserves old evidence rechecks and fresh candidates within global limits | `test_refresh_reserves_old_evidence_and_fresh_search_slots` |
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

Historical local results before review: **281 tests passed**, lint/format checks
passed, and all eight deliberate faults were detected on Python 3.15.2 with locked
dependencies. GitHub subsequently passed both Python 3.12/3.13 test jobs and the
Linux/Windows local-script jobs on commit `b77d282` in
[run 42155213334](https://github.com/skanvish11/Aletheia-core/actions/runs/42155213334).
The review supplied new failing cases beyond that original suite.

PR #17 follow-up adds `tests/test_step4_review.py`: ranking shifts must preserve old
cited evidence and same-evidence consistency checks; rejected text must stay out
of planning; and follow-up events must match actual planned work. Five new
regression cases failed on the original PR and passed after correction. Additional
coverage checks cited-source priority and successful follow-up event ordering.
The old fresh-only refresh test now checks both old and new sources with explicit
extra test capacity; default-budget regressions require an honest partial result.
Two new sensitivity checks deliberately remove refresh rechecks or leak rejected
rationale and require failure. Updated local verification: **288 tests passed**,
Ruff lint/format and whitespace checks passed, and all **ten** deliberate faults
were detected on Python 3.15.2 with locked dependencies. No live provider calls or
human passage review were performed. CI status for the updated commit is recorded
on the PR; earlier green runs do not establish the status of a later revision.

## Adversarial review before the next push

The requested adversarial review of commit `91f8032` used synthetic provider
responses through the real API and adapters, plus bounded-context unit tests.
This was a review by the implementing assistant, not an independent reviewer or
live research evaluation. Four new failing tests confirmed these findings:

| Finding | Reproduction and correction |
| --- | --- |
| High: overlapping top results hid counterevidence | Two support queries and a counter-query sharing the same top URL selected two supporting pages and returned True. Each query now advances to its next distinct URL before another query gets its turn; the fixture now returns conflicting evidence. |
| High: asymmetric refresh dropped a known contradicting source | A baseline with two supporting sources and one contradicting source refreshed only the first two when new search results were empty, changing conflict to True. Reserved rechecks now cover both cited sides. |
| Medium: rejected assessments hid an admitted conflict in planner context | Twelve rejected contradictions preceded a genuine contradiction and displaced it from the twelve-summary input. Admitted assessments now take priority within each relation. |
| Medium: baseline metadata masked fresh metadata | Refresh rediscovered a URL with an updated title/date but retained the old metadata. Current search metadata now takes precedence and the comparison exposes the change. |

All four cases failed before correction and passed afterward. A separate adversarial
case exhausted model capacity in the planning call itself: the existing implementation
correctly emitted a stop, preserved finalization capacity and announced no follow-up.
The new cases are in `tests/test_adversarial_step4.py`. Two selective mutations restore
the source-selection failures and must be detected by the regression tests. Existing
tests also exercise rejection-text isolation, duplicate/shared origins, deadline and
retry accounting, partial outcomes, saved-result immutability and citation validation.
The review does not establish resistance to every prompt injection or semantic
misjudgment; admitted source text remains untrusted model input.

Before pushing the adversarial fixes, **293 tests passed**, all **twelve** deliberate
faults were detected, and lint, formatting and whitespace checks passed locally
with the locked dependencies on Python 3.15.2. CI for the new revision is separate.

## Scope and remaining validation

One scoped assertion per request remains the V1 boundary. Compound inputs still
ask for clarification. Advanced origin detection, automatic resolution of conflicting
assessments and frontend integration are not added here. Sources remain model-assessed;
structural checks cannot prove semantic truth or genuine source independence.

This increment has offline acceptance coverage only. Live provider accuracy, latency
and human passage review remain separate evaluation work. Time/call ceilings are
unchanged from Step 2's measured starting profiles, and remain provisional for full
investigations. No claim of real-world research accuracy follows from these tests.
