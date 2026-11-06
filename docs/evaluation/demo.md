# Local and recorded demo walkthrough

Allow five to ten minutes for the presentation, with recorded fallback artifacts
prepared beforehand. Research latency is variable; do not imply every run completes
within the presentation slot. Check [the current results](results.md) before choosing
a live example. Do not describe a failed run as a successful demonstration.

## 1. Explain the scope

“Aletheia investigates one scoped claim, retrieves source passages, and returns
True, False, Almost, or an explicit unable-to-decide outcome. It keeps the evidence
and the investigation history. The output can still be wrong and needs inspection.”

## 2. Run one real claim

Follow [setup](README.md), configure providers privately, then run the one-case
evaluation command. Alternatively start the localhost service:

```sh
ALETHEIA_RESEARCH_ENABLED=true uv run --locked aletheia
```

Open `http://127.0.0.1:8000/docs`. Submit `POST /investigations` with:

```json
{"claim":"Apollo 11 landed on the Moon on July 20, 1969.","context":{"definitions":"Use UTC/GMT for the landing date, not the later first moonwalk."}}
```

Keep the returned investigation ID. Fetch its saved response and evidence from
`GET /investigations/{id}` and `GET /investigations/{id}/evidence`. The progress stream
at `/investigations/{id}/events` reports actual persisted work. An example terminal
event replay is not itself proof that a browser handled live reconnection correctly.

If the run fails or becomes partial, show that status and its limitations. Do not
replace it silently with another run. Record any retry as a new attempt.

## 3. Inspect a citation

Choose an explanation unit and follow its evidence ID to the stored excerpt and
source URL. Explain whether the passage supports that exact statement, whether its
date and scope fit, and whether another source is independent. Source excerpts are
untrusted content, not instructions. A structurally valid quote can still be irrelevant.

## 4. Demonstrate uncertainty

Use candidate `t020`, about the Wow! signal's origin, for an intended insufficient
evidence example. Its origin being unresolved should not automatically become a
False verdict. Show the actual result even if it differs from the proposed answer.
The phosphine case is a separate intended conflict example; do not conflate the two.

## 5. Reopen and refresh

Reopen the saved investigation and submit the exact same claim/context again.
The ID and stored result should match; no new provider calls should occur.
The evaluation artifact's `saved_checks` records measured behavior for these reads.

To research again, call `POST /investigations/{id}/refresh` with an empty JSON body
and a new `Idempotency-Key` header. Inspect the new version and its `/comparison`.
Repeat with the same key: it must return the same refreshed version. The original
version must remain unchanged. A new version may agree with the previous answer;
never manufacture a changed verdict for the demo.

## 6. Show evaluation honestly

Open the proposed claim worksheet and the results report. Distinguish offline
tests, actual live executions, agent inspection, and completed human review. Show
failed and partial cases along with successes. Treat Almost corrections and flag
quality as separate checks, not just label matching.

## Recorded fallback

Use saved public case artifacts from the evaluation directory. Label the view
“Recorded investigation” and show its original research timestamp and model.
Replay the saved events without suggesting they are new service calls. Preserve
failure states and limitations. Never package credentials, raw provider bodies,
private reasoning, or the local database in a public frontend.

This milestone supplies a backend/API walkthrough and public artifacts. Browser
integration and a polished hosted replay UI require their own verified client work.
Keep the unauthenticated backend on localhost; this walkthrough does not deploy it.
