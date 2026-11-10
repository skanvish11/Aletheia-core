# Visual direction

Two directions were drawn on the same content and compared in light and dark: [the design canvas](https://claude.ai/artifact/JYA3iDegSpHq61M9Sad5dC). **Chosen: Direction B, "Lab instrument".** Direction A stays on the canvas as the alternative considered.

Both are drawn on the result page (state 2.5 with 2.6 in [inventory.md](inventory.md)), because it carries the most meaning: the label, a caveat, citations, sources and the research log. Its main sample is a real claim with real sources: *"GPT-4 scored in the top 10% of test takers on the bar exam"*, from [OpenAI's GPT-4 technical report](https://arxiv.org/abs/2303.08774) and [Martínez, *Artificial Intelligence and Law*, 2024](https://doi.org/10.1007/s10506-024-09396-9). The result itself is written by hand to show the layout; Aletheia didn't produce it. The other labels use invented Northwind examples, marked as invented.

## The two directions

| | B · Lab instrument (chosen) | A · Careful editor |
| --- | --- | --- |
| Character | Precise, dense, data-forward | Exact, calm, accountable |
| Type | IBM Plex Sans; IBM Plex Mono for numbers, dates, metadata, labels and the log | Newsreader for the claim, label and headings; Public Sans for body and interface |
| Surface | Cool near-white, graphite, one cobalt accent | Warm paper, near-black ink, one oxblood accent |
| Layout | Report left, evidence pane right that follows the selected citation | One reading column; citations as sidenotes beside their sentence |
| References | Stripe docs (calm density, inline references), Linear changelog (side-by-side detail) | News fact checks (label above reasoning), Our World in Data (sources and caveats as first-class) |

**Why B:**
- **Checking a source never leaves the report.** A citation fills the evidence pane beside the sentence: relation, source, the exact excerpt, why it counts, its origin and the link. That is Aletheia's central promise, shown as a working tool rather than a footnote.
- **It shows the numbers behind a caveat.** The percentile-by-comparison-group table makes a misleading comparison visible at a glance.
- **It reads as an instrument, not a chat.** Its mono metadata, status tags and timed research log say "measured and traceable". There are no chat bubbles or generic cards.

**What B has to solve, carried into the screen reviews:**
- **Narrow screens:** the side pane only fits on wide screens. Below about 900px it stacks under the report, and a citation scrolls to it and highlights it. Whether a bottom sheet works better is a question for the result-page review.
- **Density:** B's compact rhythm risks feeling cramped on long explanations. The reading column stays at most 680px, at 17px for the conclusion.

## B's tokens

### Colour

| Token | Light | Dark | Use |
| --- | --- | --- | --- |
| `bg` | `#F5F6F8` | `#0F1216` | Page background |
| `surface` | `#FFFFFF` | `#171B21` | Header, evidence pane, panels |
| `text` | `#15181D` | `#E6E9EE` | Text |
| `text-2` | `#4B5361` | `#9BA4B1` | Secondary text, metadata, section labels |
| `rule` | `#DCE0E6` | `#2B313A` | Dividers, borders |
| `accent` | `#1F4FD1` | `#86A6FF` | Links, citations, the selected citation |
| `accent-tint` | `#E6ECFB` | `#1C2640` | Unselected citation background |
| `quote` | `#F5F6F8` | `#12161B` | Evidence excerpt background |

### Meaning

The hue for each label is a product decision, so it would stay the same under either direction. Each label is always written out, so colour never carries the meaning alone.

| Label | Text (light / dark) | Tint (light / dark) |
| --- | --- | --- |
| True | `#1F6B55` / `#7DC6A8` | `#E2EFE8` / `#1B2A24` |
| False | `#A23A2C` / `#EF9C8D` | `#F6E3DE` / `#33201C` |
| Almost | `#85600F` / `#DDB563` | `#F4EAD3` / `#30281A` |
| Insufficient evidence | `#56606B` / `#AFB7C0` | `#E7E9EC` / `#242A31` |
| Conflicting evidence | `#6E4A86` / `#CBA8E2` | `#EEE5F3` / `#2A2232` |
| Caveat | `#2D4E7A` / `#9FBCE6` | `#E4EBF4` / `#1C2536` |

In B, labels are status tags: uppercase Plex Mono, the label colour on its tint. Almost is ochre and a caveat is ink blue, so a qualified True is never mistaken for Almost.

**Contrast (WCAG 2.1):** every text pair passes AA for normal text. The lowest is the Almost tag in light mode, at 4.8:1. Body text on the page background is 16.5:1 in light mode and 15.4:1 in dark. A selected citation (surface on accent) is 6.8:1 in light mode and 7.3:1 in dark.

### Type

| Role | Face | Size / line height |
| --- | --- | --- |
| Claim | Plex Sans 600 | 30 / 1.25 |
| Result tag (TRUE, 1 CAVEAT) | Plex Mono 600, +0.06em | 14 |
| Section label (CONCLUSION, WHAT WE CHECKED) | Plex Mono 500, uppercase, +0.08em | 12, `text-2` |
| Conclusion, caveat text | Plex Sans 400 | 16–17 / 1.6 |
| Body | Plex Sans 400 | 15 / 1.55 |
| Evidence title | Plex Sans 600 | 17 / 1.35 |
| Excerpt | Plex Sans 400 italic | 15 / 1.6 |
| Metadata, dates, timings, citation numbers | Plex Mono 400–600 | 12–13 |

### Layout

- **Width:** content up to 1240px. The report column grows (at least 560px, reading width at most 680px). The evidence pane is 360–460px on the right, with a 28px gap.
- **Order of the report:** claim and status row (result tag, caveat tag, run metadata, Refresh), then the conclusion, the caveat with any numbers table, what we checked (a label and value list), limitations, and the research log.
- **Evidence pane:** shows one piece of evidence at a time, numbered as cited. It has tabs for each number, and choosing a citation in the text selects it. The selected citation is solid accent and the others are accent tint, with `aria-pressed` set.
- **Surfaces:** white panels with a 1px rule and 6px radius for the header and the evidence pane. Tints only for result tags, a caveat, an Almost correction and quotations. No shadows or coloured side borders.
- **Interaction:** focus rings use `accent`, and touch targets are at least 44px. The mock-up's 22px citation chips are their visual size; the build gives each a 44px hit area. The research log and rejected passages are collapsed `<details>`.

## Open question for review

The sample is labelled **True with a population caveat**, reading the claim as OpenAI's reported result. Read as "top 10% of test takers in general", it would be **False**: about 62nd–69th percentile. The visual direction doesn't depend on which, but the sample should match the labeling rule before it's used in a demo.
