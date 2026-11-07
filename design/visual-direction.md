# Visual direction

Two directions were drawn on the same content and compared in light and dark: [the design canvas](https://claude.ai/artifact/JYA3iDegSpHq61M9Sad5dC). **Proposed: Direction A, "Careful editor".** Direction B stays on the canvas as the alternative considered.

Both are drawn on the result page (state 2.5 with 2.6 in [inventory.md](inventory.md)), because it carries the most meaning: the label, a caveat, citations, sources and the research log. Its main sample is a real claim with real sources: *"GPT-4 scored in the top 10% of test takers on the bar exam"*, from [OpenAI's GPT-4 technical report](https://arxiv.org/abs/2303.08774) and [Martínez, *Artificial Intelligence and Law*, 2024](https://doi.org/10.1007/s10506-024-09396-9). The result itself is written by hand to show the layout; Aletheia didn't produce it. The other labels use invented Northwind examples, marked as invented.

## The two directions

| | A · Careful editor (proposed) | B · Lab instrument |
| --- | --- | --- |
| Character | Exact, calm, accountable | Precise, dense, data-forward |
| Type | Newsreader for the claim, label and headings; Public Sans for body and interface | IBM Plex Sans; IBM Plex Mono for numbers, dates, metadata and the log |
| Surface | Warm paper, near-black ink, one oxblood accent | Cool near-white, graphite, one cobalt accent |
| Layout | One reading column; citations as sidenotes beside their sentence | Report left, evidence pane right that follows the selected citation |
| References | News fact checks (label above reasoning), Our World in Data (sources and caveats as first-class) | Stripe docs (calm density), Linear changelog (side-by-side detail) |

**Why A:**
- **It reads as a judgement you can check.** The claim, label and reasoning come in order, and each sentence carries its source beside it.
- **It's further from a generic AI interface.** There are no chat bubbles and no dashboard cards.
- **It holds together without a wide screen.** B's evidence pane is its main strength, but it only exists on wide screens, and it needs state that A's sidenotes don't.

B's comparison table in the caveat (percentile by comparison group) is worth borrowing for caveats that rest on numbers.

## A's tokens

### Colour

| Token | Light | Dark | Use |
| --- | --- | --- | --- |
| `paper` | `#FAF7F0` | `#1B1916` | Page background |
| `ink` | `#1F1D1A` | `#EDE8DF` | Text |
| `ink-2` | `#575149` | `#B3AB9F` | Secondary text, metadata |
| `rule` | `#E2DBCD` | `#38332C` | Dividers |
| `accent` | `#8A2E2A` | `#E3A194` | Links and citation numbers only |
| `quote` | `#F2EDE2` | `#24211D` | Evidence excerpt background |

### Meaning

The hue for each label is a product decision, so it would stay the same under either direction. Each label is always written out, so colour never carries the meaning alone.

| Label | Text (light / dark) | Tint (light / dark) |
| --- | --- | --- |
| True | `#1F6B55` / `#7DC6A8` | `#E2EFE8` / `#1D2D26` |
| False | `#A23A2C` / `#EF9C8D` | `#F6E3DE` / `#36211D` |
| Almost | `#85600F` / `#DDB563` | `#F4EAD3` / `#332A19` |
| Insufficient evidence | `#56606B` / `#AFB7C0` | `#E7E9EC` / `#262A2E` |
| Conflicting evidence | `#6E4A86` / `#CBA8E2` | `#EEE5F3` / `#2D2434` |
| Caveat | `#2D4E7A` / `#9FBCE6` | `#E4EBF4` / `#1D2736` |

Almost is ochre and a caveat is ink blue, so a qualified True is never mistaken for Almost.

**Contrast (WCAG 2.1):** every text pair passes AA for normal text. The lowest is Almost on its tint, at 4.8:1 in light mode. Body text on paper is 15.7:1 in light mode and 14.4:1 in dark.

### Type

| Role | Face | Size / line height |
| --- | --- | --- |
| Result label | Newsreader 600 | 60 / 1.05 ("with a caveat": 40, italic, `ink-2`) |
| Claim | Newsreader 500 | 44 / 1.18 |
| Section heading | Newsreader 500 | 26 |
| Scoped assertion, quotations | Newsreader 400 | 18–21 / 1.5 |
| Explanation | Public Sans 400 | 19 / 1.6 |
| Body | Public Sans 400 | 16–17 / 1.6 |
| Metadata, sidenotes | Public Sans 400–600 | 13–15 |
| Eyebrows ("Claim", flag type) | Public Sans 600, uppercase, +0.06–0.08em | 13 |

### Layout

- **Width:** content up to 1040px. The reading column stays at most 680px.
- **Sidenotes:** a 260px column beside the reading column, 56px gap. Below about 900px each sidenote drops under its sentence.
- **Vertical rhythm:** 56–72px between major sections. A 2px `ink` rule above the conclusion is the page's one strong line.
- **Surfaces:** tinted blocks only for a caveat, an Almost correction and quotations. No cards, shadows or coloured side borders.
- **Interaction:** focus rings use `accent`, and touch targets are at least 44px. A citation jumps to its source entry; on wide screens a preview opens in place. The research log and rejected passages are collapsed `<details>`.

## Open question for review

The sample is labelled **True with a population caveat**, reading the claim as OpenAI's reported result. Read as "top 10% of test takers in general", it would be **False**: about 62nd–69th percentile. The visual direction doesn't depend on which, but the sample should match the labeling rule before it's used in a demo.
