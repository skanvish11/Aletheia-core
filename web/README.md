# Aletheia web client

Companion demo client for the backend described in the root [README](../README.md), sections 9 and 11. It is a static React + TypeScript app built with Vite. It never hosts or exposes the backend.

## Modes

| Mode | How to run | What it does |
| --- | --- | --- |
| Replay (default) | `npm run dev` | Plays bundled recordings from `src/fixtures/`. No backend calls; every view is labeled **Recorded investigation**. This is the only mode allowed on a hosted deploy. |
| Live | `VITE_DATA_SOURCE=live npm run dev` | Talks to the local backend through the dev-server proxy at `/api`. Set `ALETHEIA_API_URL` if the backend is not on `http://127.0.0.1:8000`. Localhost only. **Requires the Aletheia backend, which is still being built**; this command starts only the client. |

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
- **Report** (saved samples open straight to it; "Replay research steps" plays the recorded progress): the claim, then the verdict with its qualification caveat and an evidence-linked summary, then how the verdict was reached, limitations, and sources. The research log is collapsed at the end.
- **Results that fail to load:** if research ends but fetching the report fails, the page says so and offers "Retry loading results", which never starts a new investigation.
- **Citations:** numbered links open an accessible preview of the source and excerpt (Esc or an outside click closes it, and focus returns to the link). Without popover support they jump to the evidence entry.

## Status and caveats

- `src/api/types.ts` is **provisional**. Field names are inferred from the design doc; reconcile them with `src/aletheia/contracts.py` once it exists.
- The only recording is invented sample data (`sample: true`), and the page says so. Replace it with sanitized exports of real runs before any hosted demo, and review exports for secrets first.
- Clarification, failed and partial results render in the shared layout, but their full designs and sample recordings come in a follow-up.
- The refresh, saved-view and comparison screens are not built yet.
