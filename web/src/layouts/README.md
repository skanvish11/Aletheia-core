# ALETHEIA evidence layouts

Open **ALETHEIA.html** for Layout A or **ALETHEIA-C.html** for Layout C. Both standalone previews open directly in a browser and include the three sample claims and their saved source excerpts.

Both versions share the fingerprint landing page, verdict summary, numbered citations, and limitations. Layout A expands individual evidence rows. Layout C presents short source takeaways in a three-column grid with quote toggles and stacks the cards on mobile.

## Run the editable version

From the repository’s `web` directory, run `npm ci` and `npm run dev`. Open `/src/layouts/index.html` for Layout A or `/src/layouts/index.html?layout=c` for Layout C. To investigate custom claims, start the research-enabled backend and run the dev server with `VITE_DATA_SOURCE=live`. The editable versions use the web client’s existing investigation API.

Run `npm test` from `web` for the frontend suite. The layout tests cover sample navigation, restored reports, source links, matched quotes, unavailable live research, and card takeaway lengths.
