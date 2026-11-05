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

## Status and caveats

- `src/api/types.ts` is **provisional**. Field names are inferred from the design doc; reconcile them with `src/aletheia/contracts.py` once it exists.
- The only recording is invented sample data (`sample: true`), and the page says so. Replace it with sanitized exports of real runs before any hosted demo, and review exports for secrets first.
- The refresh, saved-view and comparison screens are not built yet.
