# Page and state inventory

Every page the `web/` client has, and every state within each page, taken from the backend contract (`contracts.py`, `research_contracts.py`, the API routes and `docs/research-pipeline.md`). This is the list the screens will be designed and reviewed against, one at a time. Visual direction comes after this list is agreed.

**Pages vs states.** A *page* has its own address and survives a reload. A *state* is a condition within a page, decided by what the backend returns. There are two pages.

| Page | Address | Purpose |
| --- | --- | --- |
| [1. Check a claim](#1-check-a-claim) | `/` | Enter a claim, or (recorded mode) pick a recorded investigation. |
| [2. Investigation](#2-investigation) | `/investigations/<id>` | One investigation from queued to result, including its evidence. Reloading or reopening the address shows its saved state (a saved read; no new provider calls). |

The client has no addresses today; giving each investigation one is part of this work.

## 1. Check a claim

| State | When | What the person sees and can do |
| --- | --- | --- |
| 1.1 Checking the backend | On load, until `/health` answers or 8 s pass | The claim field, disabled, with "Checking the backend…". |
| 1.2 Backend not reachable | `/health` fails or times out | Why, how to start the backend, and **Retry connection**. Rechecks on window focus and when the browser comes back online. |
| 1.3 Research turned off | `/health` ok, `research_enabled: false` | That new claims would stay queued; restart with `ALETHEIA_RESEARCH_ENABLED=true`. **Retry connection**. |
| 1.4 Ready | `/health` ok, research enabled | Claim field (up to 8,000 characters) and optional context: timeframe, location, definitions, notes. **Investigate**. |
| 1.5 Submitting | After Investigate, until the backend answers | Button reads "Starting investigation…"; repeat submissions ignored. Then go to page 2. |
| 1.6 Submission rejected | `413` too long, `422` invalid, `503` busy, or unreachable | Plain-language reason next to the form; the typed claim and context are kept. |
| 1.7 Recorded mode | The hosted, replay-only client | No claim form. A list of recorded investigations, each showing its claim and result label, every view marked **Recorded investigation**. |

Submitting the same claim and context again returns the saved investigation instead of starting research; page 2 then says it's a **saved result** (2.6).

## 2. Investigation

The page always starts with the claim and its context, then shows one of the states below.

### Before a result

| State | When (`status`, events) | What the person sees and can do |
| --- | --- | --- |
| 2.1 Waiting | `queued` | "Waiting to start". If research is turned off, say it stays queued until it's turned on. |
| 2.2 Researching | `running`; progress events stream in | A live research log, in plain language: interpreting the claim, the route chosen (quick check or deeper research), searches planned and run, sources read, sources rejected or deferred, evidence checked, escalation to deeper research, follow-up rounds, budget or round limits reached, and writing the conclusion. Never private model reasoning. |
| 2.2a Reconnecting | The progress stream drops | A quiet notice; clears when events resume. Missed events are replayed, not lost. |
| 2.2b Progress unavailable | The stream closes before research ends | Say progress can't be followed; the investigation is saved, and reloading the page shows its state. |
| 2.3 Needs clarification | `needs_clarification`, `clarification_questions` | The backend's questions, each beside a field to answer it. Submitting starts a **new** investigation with the answers added as context (the current one ends here; V1 has no resuming). |
| 2.4 Loading the result | Terminal event received, result and evidence not yet loaded | "Research finished. Loading the results…". |
| 2.4a Result didn't load | Loading fails or takes more than 20 s | Why, that the investigation is saved, and **Retry loading results** (fetches again; never starts research). |

### The result

`completed` or `partial`, with a validated result. The label comes from the decision fields, never from `status`:

| State | Decision | Shows |
| --- | --- | --- |
| 2.5a True | `decided`, `"true"` | Label, cited explanation. |
| 2.5b False | `decided`, `"false"` | Label, cited explanation. |
| 2.5c Almost | `decided`, `"almost"` | Label and the three cited correction parts: what's correct, what needs correcting, the corrected claim. |
| 2.5d Insufficient evidence | `unable_to_decide`, `insufficient_evidence` | Label and why the evidence doesn't settle it. Not a truth verdict, but an explicit result. |
| 2.5e Conflicting evidence | `unable_to_decide`, `conflicting_evidence` | Label and which admissible sources disagree. Never shown as Almost. |

Each result page then has these parts, in this order:

1. **Conclusion:** the label, any caveat flags, the correction (Almost), and the cited explanation. If the explanation is empty or cites nothing, the conclusion still links the evidence behind the decision.
2. **What we checked:** the scoped assertion, the route, the scope note, and whether comparisons and scope were assessed.
3. **Limitations:** saved limitations, deduplicated.
4. **Sources:** admitted evidence first, numbered as cited; passages checked but not admitted collapsed, with why.
5. **Research log:** the steps from 2.2, collapsed.

**Evidence stays inside the page.** A numbered citation opens a preview: source title and date, its relation to the claim (supports, contradicts, context), the exact excerpt, and a link to the original. The full entry is in Sources. There is no separate evidence page, so every statement can be checked without losing your place.

### Modifiers on any result

These combine with any of 2.5a–e:

| State | When | Shows |
| --- | --- | --- |
| 2.6a Caveat | One or more `qualification_flags` | Each flag: misleading comparison or narrower than claimed, its dimension (population, timeframe, units, baseline, condition, jurisdiction, definition, evaluation setup, benchmark subset), the explanation and citations. A flag never changes the label. |
| 2.6b Partial run | `partial` | The run stopped before every step finished, why (`stop_reason`), and that Limitations says what was unfinished. Never invent reduced source coverage. |
| 2.6c Saved result | The submit response has `reused: true` | That this is the saved result of an earlier identical check, with its original research time. |
| 2.6d Later version | `version` > 1 | "Version N", linked to the earlier version. |
| 2.6e Recorded | Recorded mode | **Recorded investigation** with the original research time; **Replay research steps** replays the log, without pretending it's a live call. |

### Refresh and what changed

Built after the result screens; designed now so the page leaves room for it.

| State | When | Shows |
| --- | --- | --- |
| 2.7 Refresh | A finished or failed investigation (live mode only) | **Refresh** re-runs research as a new version at a new address (2.2 onward). Refreshing an active or clarification-needed run is refused (`409`), so the action isn't offered there. |
| 2.8 What changed | `version` > 1, from `/comparison` | Against the earlier version: whether the decision or verdict changed, whether the scope changed, sources added, removed or changed, and any inconsistency flagged. While research runs: "Comparing once research finishes". `unavailable` and `not_applicable` say so plainly. |

### Not a result

| State | When | Shows |
| --- | --- | --- |
| 2.9 Failed | `failed`, no result | The backend's error message and stop reason. Never shown as Insufficient evidence. **Refresh** (2.7) where allowed. |
| 2.10 Not found | `404` | That no investigation has this address, and a way back to page 1. |

## Considered and left out of V1

- **History or recent checks:** the backend can't list investigations. A browser-only list of recent checks is possible later.
- **Accounts, sharing, public links:** out of V1 scope; the live backend is localhost-only and is never exposed.
- **Several assertions per claim:** compound claims get clarification (2.3) instead.
- **Chat or follow-up questions:** out of scope, so no conversational layout.

## Next

1. Agree this inventory.
2. Two visual directions (typography, spacing, hierarchy, interaction, a restrained accessible palette), shown on real product content: the five result labels, a caveat, an Almost correction, and the research log.
3. Design and review each screen in turn, in this order: 2.5 result (with 2.6), 2.2 researching, 1 check a claim, 2.3 clarification, 2.4/2.9/2.10 recovery and failure, 2.7–2.8 refresh.
