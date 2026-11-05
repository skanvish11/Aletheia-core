# Aletheia web client

Companion demo client for the backend described in the root [README](../README.md), sections 9 and 11. It is a static React + TypeScript app built with Vite. It never hosts or exposes the backend.

## Modes

| Mode | How to run | What it does |
| --- | --- | --- |
| Replay (default) | `npm run dev` | Plays bundled recordings from `src/fixtures/`. No backend calls; every view is labeled **Recorded investigation**. This is the only mode allowed on a hosted deploy. |
| Live | `VITE_DATA_SOURCE=live npm run dev` | Talks to the local backend through the dev-server proxy at `/api`. Set `ALETHEIA_API_URL` if the backend is not on `http://127.0.0.1:8000`. Localhost only. |

## Commands

```sh
npm install
npm run dev      # http://127.0.0.1:5173
npm run build    # type-check and build to dist/
npm run lint
```

## Screens

- **Entry:** live mode leads with the claim field and an Investigate button. Replay mode introduces the product, lists the sample investigations, and explains how to investigate your own claim locally. It never shows a submit button that can't work.
- **Researching:** the claim headline, the latest step, and the live progress log.
- **Report:** the claim, then the verdict with its qualification caveat and an evidence-linked summary, then how the verdict was reached, limitations, and sources. The research log is collapsed at the end.
- **Citations:** numbered links open an accessible preview of the source and excerpt (Esc or an outside click closes it, and focus returns to the link). Without popover support they jump to the evidence entry.

## Status and caveats

- `src/api/types.ts` is **provisional**. Field names are inferred from the design doc; reconcile them with `src/aletheia/contracts.py` once it exists.
- The only recording is invented sample data (`sample: true`), and the page says so. Replace it with sanitized exports of real runs before any hosted demo, and review exports for secrets first.
- Clarification, failed and partial results render in the shared layout, but their full designs and sample recordings come in a follow-up.
- The refresh, saved-view and comparison screens are not built yet.
