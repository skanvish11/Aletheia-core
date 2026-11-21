# Aletheia

Aletheia builds a citation trail for the claim you have in mind.

> ODSC × Nebius Hackathon submission · Challenge: *Build a research agent that brings its sources*

- **Demo video (2–3 min):** Link pending.
- **Team:** [@skanvish11](https://github.com/skanvish11) · [@csalive](https://github.com/csalive)

## The problem and the product

**Remember reading it somewhere?** A reporter recalls a figure they've seen in several places. A scientist recalls a finding from a paper read months ago. Writing the sentence is easy. Citing it means piecing together which source said what.

Aletheia builds that citation trail. You give it the claim as you remember it, and it brings back the exact passages, each linked to the page it came from. Every passage is checked word for word against the saved page. Aletheia then says whether the sources show the claim is **true** or **false**, or that they **cannot settle** it. You see which details hold up, fix the sentence where your memory slipped, and give readers a trail they can follow.

## How it works

```text
Claim → plan queries (incl. fact-checks) → search and read pages → check the sources → propose a verdict with quotations → check the quotations
```

- **Query planning:** The model writes up to three queries, including one aimed at fact-checks and evidence that the claim is false. Tavily searches them in parallel. If the first round leaves the claim unresolved, the agent can search once more for the missing detail.
- **Evidence handling:** The agent merges results, prioritizes government, academic, and international-body domains, and drops duplicate URLs and page text. The model reads selected passages and proposes a verdict with quotations. For **true** or **false**, Python must locate at least one usable quotation in the saved page. A second model call can veto the verdict if the quotations point the other way. If that check is inconclusive or cannot run, the proposed verdict stands. [Research loop](src/aletheia/simple.py)
- **Source checks:** Social and video sites are skipped. Pages with nearly the same wording, and subdomains of one site, count as one source. A true or false verdict needs at least one quotation from a recognised source: an official body, a major news organization, a journal or a reference publisher. A claim stated only on unrecognised sites returns **cannot settle**. A fact-check that contradicts the claim outweighs unrecognised pages. Each quotation in the report is labelled with whether its site is recognised.
- **Protection against bad actors:** Several sites repeating a claim count for no more than one unrecognised site, so a planted claim can't reach a verdict on its own. Page text can't give the model instructions: it enters as untrusted data, and links are removed from the reason shown to the user. Every quotation must appear word for word on the saved page, so the model can't invent a source.
- **Safety:** Web pages enter the model as untrusted text. Python runs the searches and page reads and enforces the limits. Provider keys stay on the backend. The local API binds to loopback.
- **Trade-offs:** Parallel searches and page reads save time. One follow-up limits cost but can leave a difficult claim unresolved. A quotation can be genuine and still be misinterpreted. In two live evaluations, DeepSeek matched the expected answer on **66 of 77 tuning claims** each time, although 13 answers changed between runs. The second run had a **28-second median**. [Evaluation details](docs/hackathon-status.md#where-accuracy-stands)

## Required services

| Requirement | How we use it |
| --- | --- |
| Nebius Token Factory (inference) | The demo configures `deepseek-ai/DeepSeek-V4-Pro-0813` through `NEBIUS_MODEL`. The model plans searches, proposes a verdict with quotations, and checks the verdict against those quotations. |
| Tavily (real-time web search) | Search finds candidate pages. Extract retrieves their text. The agent reads up to six pages in its first round and up to three additional pages in a follow-up. |

## Setup

Use Python 3.12+, uv, and Node.js 22.12+ with npm. Clone the repo and create your local configuration:

```bash
git clone https://github.com/skanvish11/Aletheia-core.git
cd Aletheia-core
cp .env.example .env
```

Add your `NEBIUS_API_KEY` and `TAVILY_API_KEY` to `.env`. The example already selects DeepSeek and enables the simple research loop. Start the API:

```bash
uv sync --locked
uv run --locked aletheia
```

In a second terminal, start from the cloned repository root:

```bash
cd web
npm ci
VITE_DATA_SOURCE=live npm run dev
```

Open the URL printed by Vite and enter a claim. The research log shows the searches and page reads. The finished report links to the source passages. To explore the bundled examples without keys, run `npm run dev` from `web/` in a fresh terminal. [Web client guide](web/README.md)

## Example

**Claim** — “The Apollo 11 lunar module landed on the Moon on 20 July 1969.”

**Recorded verdict** — **True.** The cited records date the lunar module’s touchdown to July 20, 1969.

| Source | What the agent found |
| --- | --- |
| [National Air and Space Museum](https://airandspace.si.edu/explore/stories/apollo-missions/apollo-11-moon-landing/apollo-11-timeline) | “The lunar module touched down on the surface on the Moon.” |
| [The Planetary Society](https://www.planetary.org/space-missions/apollo-11) | “The official touchdown time was 20:17:39 UTC on 20 July 1969.” |
| [Wikipedia](https://en.wikipedia.org/wiki/Apollo_11) | “July 20, 1969” |

**Aletheia run**

1. **3 searches** returned **15 results**.
2. Aletheia retrieved **6 pages** and cited **3 sources**.
3. In **14.3 seconds** from start to verdict, it matched the event described in the museum’s timeline to the date in the other two sources.

[Saved Apollo 11 investigation](web/src/fixtures/live/apollo-11-landing-date.json)

## Failure / insufficient-evidence case

**Claim** — “Exactly 87 hikers reached Mount Whitney’s California summit on July 1, 2001.”

**Recorded verdict** — **Cannot settle.** The pages give annual permit and trail-use figures. None gives a summit count for July 1.

| Source | What the agent found |
| --- | --- |
| [Mount Whitney Portal Message Board](https://www.mountwhitneyforum.com/ubbthreads.php?ubb=showflat&Number=86573) | “The summit log is not an accurate accounting.” |

**Aletheia run**

1. **6 searches** returned **30 results**.
2. Aletheia retrieved **9 pages** and cited **1 source**.
3. In **48.6 seconds** from start to verdict, it completed a follow-up search for a daily count. The figure of 87 remained unverified.

[Saved Mount Whitney investigation](evals/runs/20261117-simple-live-dsv4pro-a/claims/u-05.json) · [Demo script, scene 6](docs/demo-script.md)

## Limitations

- **Coordinated sites.** A group of sites set up to repeat a false claim can still slip through if one of them is recognised. Spotting such networks needs signals Aletheia doesn't collect yet: domain age, shared hosting or ownership, and sites that only cite each other.
- **Independent origins.** Two sources may both repeat a third. The earlier staged pipeline records whether sources are independent. The simple loop doesn't use that check yet.
- **Recognised sources can be wrong.** An official or well-known page can be outdated or mistaken. Aletheia shows the sentence and its source so the reader can judge.
- **Interpretation.** A quotation can be genuine and still be misread. A second model call checks the direction, but if it is inconclusive the verdict stands.

## License

[MIT](LICENSE)
