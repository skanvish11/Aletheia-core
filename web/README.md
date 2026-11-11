# Aletheia web client

Companion demo client for the backend described in the root [README](../README.md), sections 9 and 11. It is a static React + TypeScript app built with Vite. It never hosts or exposes the backend.

## Modes

| Mode | How to run | What it does |
| --- | --- | --- |
| Replay (default) | `npm run dev` | Plays bundled recordings from `src/fixtures/`. No backend calls; every view is labeled **Recorded investigation**. This is the only mode allowed on a hosted deploy. |
| Live | `VITE_DATA_SOURCE=live npm run dev` | Talks to the local backend through the dev-server proxy at `/api`. Set `ALETHEIA_API_URL` if the backend is not on `http://127.0.0.1:8000`. Localhost only. This command starts only the client; run the backend separately (root README). On load the client calls `GET /health`, and the claim field is enabled only when the backend answers **and** reports `research_enabled: true`. Otherwise it explains why (unreachable, or research not enabled yet). |

## Commands

```sh
npm install
npm run dev      # http://127.0.0.1:5173
npm run build    # type-check and build to dist/
npm run lint
npm test         # hook and form behavior (Vitest + jsdom)
```

## Screens

- **Entry:** the claim field is always the first thing on the page. In live mode it submits; while a submission is pending the button reads "Starting investigation…" and further clicks are ignored. In replay mode the field is disabled, with a note that live investigation needs the backend, which is still being built. Sample investigations are listed below it.
- **Researching:** the claim headline, the latest step, and the live progress log.
- **Report** (saved samples open straight to it; "Replay research steps" plays the recorded progress), in visual direction B ([`design/visual-direction.md`](../design/visual-direction.md)): the claim, the result label just below it in its label colour (smaller than the claim), and one mono line of run facts. Below, the report on the left (the evidence-linked conclusion, any correction or caveat, what was checked, limitations, and the collapsed research log) and the evidence pane on the right.
- **Results that fail to load:** if research ends but fetching the report fails, the page says so and offers "Retry loading results", which never starts a new investigation.
- **Evidence pane:** shows one piece of evidence at a time, numbered as cited: relation, source, the exact excerpt, why it counts, and a link to the original. Choosing a citation in the report, or a numbered tab in the pane, selects it (`aria-pressed`). Passages checked but not admitted are collapsed at the bottom of the pane. Below 900px the pane stacks under the report, and choosing a citation scrolls to it.

## Status and caveats

- `src/api/types.ts` is **reconciled** with `src/aletheia/contracts.py` and the backend's `/openapi.json` for investigations, context, links, errors and `/health`. Results, evidence and most event payloads are still provisional because the backend doesn't serve them yet.
- If the progress stream closes before research finishes (for example, `/events` returns 404 on a backend without the research pipeline), the page says live progress isn't available instead of staying on "Researching".
- The only recording is invented sample data (`sample: true`), and the page says so. Replace it with sanitized exports of real runs before any hosted demo, and review exports for secrets first.
- Clarification, failed and partial results render in the shared layout, but their full designs and sample recordings come in a follow-up.
- The refresh, saved-view and comparison screens are not built yet.
