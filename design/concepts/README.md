# Aletheia design concepts

Two clickable design directions for review, as requested on #4. **Design concepts only:** research is simulated, the data is invented, and nothing here calls the backend. The product client lives in `web/` and is unaffected.

```sh
cd design/concepts
npm install
npm run dev     # http://127.0.0.1:5173
```

The top bar switches **concept** and **sample outcome**. The URL hash records both (`#a/caveat`, `#b/insufficient`), so a specific view can be linked.

## What to look at

| Concept | Direction | Built with |
| --- | --- | --- |
| **A · Focused checker** | One claim field, then an editorial answer. On desktop, evidence opens in a panel **beside** the answer; on mobile, in a bottom sheet. | AI Elements (Prompt Input, Suggestion, Task) + shadcn/ui (Sheet, Button) |
| **B · Conversational** | The claim is a message; the answer is a report card inside the reply. Evidence opens in a sheet (right side on desktop, bottom on mobile). | assistant-ui primitives with an external-store runtime + shadcn/ui Sheet |

Each concept covers entry, submitting, researching (with "Skip to the answer"), the completed answer, and a citation opened. Switch the sample to **Insufficient evidence** for the unhappy path.

**How simulation is labeled:** the top bar always reads "Design concept · simulated research · invented sample data". If you type your own claim, a "Simulated" note says the concept is playing back a sample instead. The skip link reads "(simulation only)".

Both concepts share the same sample content and the same evidence detail (`src/shared/evidence.tsx`): source identity and date, relation to the claim, the exact excerpt, why it matters, limitations, the original link, and collapsed citation details (spans, retrieval time, URL).

## Against the review questions

| Question | A · Focused checker | B · Conversational |
| --- | --- | --- |
| Can users find where to enter a claim? | Yes: a large field with an Investigate button, plus examples. | Yes: a composer at the bottom, plus examples on the empty screen. |
| Verdict and caveat at a glance? | Yes: verdict, one-line answer and caveat callout fit the first mobile screen. | Yes, inside the reply card. The claim scrolls up as a chat bubble. |
| Inspect a source without losing your place? | **Desktop: yes**, the panel sits beside the answer and highlights every citation of that source. Mobile: a sheet covers the lower part. | **No on desktop:** the modal sheet blurs and covers the answer. Mobile: same as A. |
| How much competes on the first screen? | Little: answer first; findings, limitations and activity below. | A little more: chat chrome, the claim bubble and the activity line sit above the answer. |
| Keyboard | Citations are buttons; Esc closes the panel; focus returns to the citation. | Same; Esc closes the sheet; focus returns to the citation. |

**My read:** A fits Aletheia's "answer → caveat → evidence" flow better. B's conversation framing implies follow-up chat, which is out of scope, and its modal evidence loses the reader's place. B would make sense if clarification and follow-up questions become central later.

## Library evaluation

| | shadcn/ui | AI Elements | assistant-ui |
| --- | --- | --- | --- |
| License | MIT | Apache-2.0 | MIT |
| Install model | Component source copied into the repo | Copied source via the shadcn registry | npm packages, plus optional copied components |
| Works with our Vite + React 19 + TS client | Yes | Yes | Yes |
| Requires | Tailwind v4, Radix (chosen) or Base UI | shadcn/ui; Prompt Input imports types from `ai` (Vercel AI SDK) — dev dependency only | Nothing chat-backend-specific with the external-store runtime; brings `zustand` and its own core packages |

Findings while building:
- **AI Elements' Inline Citation is a Radix Hover Card.** It opens on hover or focus only, not on tap, and Radix hover cards are intended for sighted mouse users. I used our own citation buttons that open the evidence panel instead.
- **AI Elements' Chain of Thought** wasn't used: we must not show private model reasoning.
- **Its Prompt Input is large** (about 1,500 lines with attachments, screenshots and model selectors). We use only the textarea, footer and submit parts.
- **The AI Elements CLI is being deprecated** (end of November 2026) in favor of shadcn registry URLs, and running it without component names installs every component and about 20 dependencies. Add components by URL: `npx shadcn add https://elements.ai-sdk.dev/api/registry/<name>.json`.
- **assistant-ui renders our report as a data part** (`data-investigation`), so the answer layout is app-defined, never model-generated. Its built-in "running" placeholder had to be turned off, since our report shows its own progress.
- **Dependency audit:** `npm audit` reports only issues inside the `shadcn` CLI's own dependencies, which is a dev-only tool; nothing ships to the browser.
- **Bundle:** both concepts together build to about 711 kB (218 kB gzipped), including both libraries and the Geist font. A single chosen direction would be smaller.

## Not decided here

Shared tokens (type scale, spacing, widths, semantic colors, focus styles) and the full component states (clarification, partial, failed, retry) come after a direction is chosen.
