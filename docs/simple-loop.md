# The simple search-and-verdict loop

An alternative to the staged pipeline for one claim. It is off by default. Turn it on
with `ALETHEIA_PIPELINE=simple` alongside `ALETHEIA_RESEARCH_ENABLED=true`:

```sh
ALETHEIA_RESEARCH_ENABLED=true ALETHEIA_PIPELINE=simple uv run --locked aletheia
```

The API, the saved records and the event types are unchanged, so existing clients
keep working.

## What it does

1. **Plan.** One model call writes up to three search queries from the claim. If that
   call fails, the claim text itself is the query.
2. **Search and read.** Each query runs through Tavily search. Results are taken in
   turn across queries (every query's best hit before any query's second). Social and
   video sites are not read, and government, academic and international-body sites
   are read first. Duplicates are dropped by URL and by page content, and up to six
   pages are extracted and saved.
3. **Judge.** One model call (`aletheia.one_call`, the call the trusted evaluation
   measures) sees the claim and the most relevant passages of up to six pages. It
   returns `true`, `false` or `cannot_settle`, up to four quotations and a reason.
4. **Check the quotations.** A quotation counts only if it is found word for word in
   the saved page, has at least three words, shares a word with the claim, and starts
   and ends on word boundaries. A `true` or `false` answer with no such quotation is
   treated as `cannot_settle`. Links are removed from the model's reason.
5. **Check the basis.** The verdict call also says, for each page it relies on, what
   basis the page offers (see below). Code decides from that whether a true or false
   verdict can stand. If not, the answer becomes `cannot_settle` with a reason that
   says what is missing, and any original record the pages name but that was not read
   becomes the follow-up search's target.
6. **Check the verdict against its quotations.** A second, small model call sees only
   the claim and the accepted quotations and says which way they point. If they point
   the opposite way to the verdict, the verdict is withdrawn and treated as
   `cannot_settle`. An unclear reading leaves the verdict standing.
7. **Follow up once.** If the answer is `cannot_settle`, one more plan call gets the
   model's reason as "what is missing", up to three new pages are read, and the judge
   call runs once more. The new pages are always among the six it sees. Then the loop
   stops.

Page text reaches the model only as data in the user message. The instructions are
fixed and tell the model not to follow instructions found inside pages.

## The basis check

A page can show that someone *said* something without showing that it is *true*. A
manufacturer's "up to 20 hours" proves the advertisement, not a test result, and a
thousand pages repeating it are still one source. So for each page it relies on, the
verdict call reports: the basis (`documented_record`, `statement_or_announcement`,
`secondhand_report`, `personal_anecdote` or `unsupported_assertion`), the underlying
record, who produced it, whether this page is the producer's own publication or reports
someone else's, whether the site belongs to the producer, the recorded test conditions
and date, and passages copied word for word that show these. It writes `unknown` when a
page does not say. It also says whether the claim is about the fact itself or about what
a named source said or published, and whether the result depends on test conditions.

**Enforced in code** (`basis_check` in `aletheia/one_call.py`), for true and false alike:

- A page earns credit only if it carries an accepted verdict quotation and every
  provenance passage is found word for word on it.
- Its producer and record must be known. If the result depends on how it was
  measured, the recorded conditions must be known too.
- **One page settles the claim** only if it is the producer's own publication on the
  producer's own site, and it is a documented record (a claim about the fact) or the
  named source's own record or statement (a claim about what that source said).
- **Otherwise, documented records from two different producers are needed.** Reports
  of one producer's record count once, and unknown producers count for nothing. Claims
  about what a named source said have no such route.
- The `authoritative_record`, `origin`, `publisher`, `independence` and provenance
  fields of saved evidence are filled from these readings; only a page the code
  credited is marked authoritative.

**Still the model's judgment:** whether a page is really a documented record rather
than a statement, who produced it, whether the site belongs to that producer, whether
the recorded conditions match the claim's, and whether the claim is about the fact or
about what someone said. Code cannot verify these; it only checks that the passages
given for them are on the page and that the combination meets the rules.

## When it stops, and what it reports

| Situation | Status | Stop reason | Verdict |
| --- | --- | --- | --- |
| True or false with a usable quotation | completed | `evidence_sufficient` | true / false |
| Not settled after the follow-up, or the follow-up found nothing new | completed | `budget_exhausted` | none |
| The first search found no results | completed | `no_useful_query` | none |
| No page was added because a search or page retrieval failed | partial | `provider_failure` | none |
| The model's answer could not be used | partial | `invalid_task_output` | none |
| Time or call limit reached | partial | the limit's name | from the pages read, if settled |
| Credentials rejected or quota exhausted | failed | `provider_failure` | no result |

A limit reached while searching or reading stops the gathering, not the round: the
pages already read are still judged.

Without a verdict the result is `unable_to_decide` with `insufficient_evidence`, and
the model's reason is listed under limitations.

## Limits per claim

At most 6 model calls, 6 searches and 13 page reads (6 + 3 pages, with two spare tries
per round for pages that cannot be read), within 150 seconds. The budget is counted in
attempts and allows three attempts per call, so a provider retry does not use up a
later call.

## What it does not do

It does not produce the "almost" verdict, qualification flags or component findings.
Those belong to the staged pipeline. The staged pipeline's own evidence routes
(`sufficient` in `aletheia/verdicts.py`) are unchanged by the basis check and were not
measured by the provenance evaluation.

## Measuring it

`scripts/evaluate_research.py --pipeline simple` runs the loop through the same
runner as the staged pipeline, including `--replay-evidence` on saved pages.
`scripts/evaluate_provenance.py` runs the verdict stage on the frozen packets in
[`evals/provenance`](../evals/provenance/README.md).
