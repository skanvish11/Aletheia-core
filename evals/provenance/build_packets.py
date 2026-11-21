"""Build the frozen provenance evaluation packets.

Run once to write `packets.json` (what the model sees) and `answers.json` (expected
outcomes, known origins and rationale, never sent to the model). Both files are
committed; `packets.sha256` freezes them. Rebuilding must reproduce the same hash.

Three supported cases use real pages saved during earlier runs (evals/evidence). The
other pages are written for this set: the entities are fictional, so where each page's
claim came from is known exactly. Fictional names appear in BOTH groups (7 of the 10
supported claims), so a made-up name cannot decide the verdict.

    uv run python evals/provenance/build_packets.py
"""

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).parent
EVIDENCE = HERE.parent / "evidence" / "pages"
RETRIEVED = "2026-11-19T00:00:00Z"


def saved(claim_id, url_part):
    pages = json.load(gzip.open(EVIDENCE / f"{claim_id}.json.gz"))
    page = next(p for p in pages if url_part in p["url"])
    return {
        "url": page["url"],
        "title": page["title"],
        "text": page["original_text"],
        "saved_from": f"evals/evidence/pages/{claim_id}.json.gz",
    }


def page(url, title, text):
    return {"url": url, "title": title, "text": text.strip()}


# --- Shared packets -----------------------------------------------------------------

VOLTREON = [
    page(
        "https://www.voltreonlabs.com/reports/2025/kestrel-7-battery",
        "Kestrel 7 battery test report | Voltreon Labs",
        """
# Kestrel 7: battery test report

Report VL-2025-0412 · Published 14 May 2025 · Voltreon Labs, Device Testing Group

## Method

We tested two retail Kestrel 7 units (firmware 3.2.1) bought at retail. Each unit was
charged to 100% and then looped a 1080p video file stored on the device until it shut
down. Screen brightness was fixed at 200 nits, Wi-Fi was on and connected, Bluetooth
was off, and the room was held at 22 °C. Each unit ran the test twice.

## Result

In our continuous video-playback test, the Kestrel 7 ran for 20 hours 6 minutes on
average (unit A: 20 h 2 min and 20 h 9 min; unit B: 20 h 4 min and 20 h 9 min).

We did not run a web-browsing or gaming test on this model.
""",
    ),
    page(
        "https://www.gadgetline.news/kestrel-7-battery-life-tested",
        "Kestrel 7 lasts about 20 hours in lab video test",
        """
# Kestrel 7 lasts about 20 hours in lab video test

The Kestrel 7 tablet lasted just over 20 hours in a continuous video-playback test run
by Voltreon Labs, according to the lab's published report. Voltreon looped a 1080p
video at 200 nits until the battery ran out. The tablet goes on sale in June.
""",
    ),
]

CORVANE = [
    page(
        "https://www.corvane.com/newsroom/2025/introducing-x2",
        "Introducing Corvane X2 | Corvane Newsroom",
        """
# Introducing Corvane X2

Press release · 3 March 2025

Corvane today announced the X2, its thinnest tablet yet. The Corvane X2 offers up to
20 hours of battery life*, an 11-inch display and a new aluminium design.

"The X2 is built for people who are away from a charger all day," said Corvane chief
product officer Lena Brandt.

*Battery life is a Corvane estimate. Actual results vary with use and settings.
""",
    ),
    page(
        "https://www.techbrief.io/corvane-x2-20-hour-battery",
        "Corvane X2 tablet: 20-hour battery, thinnest design yet",
        """
# Corvane X2 tablet: 20-hour battery, thinnest design yet

Corvane's new X2 tablet runs for 20 hours on a charge, the company announced on
Monday. The X2 also brings an 11-inch display.
""",
    ),
    page(
        "https://www.dailydevice.com/news/corvane-x2-battery",
        "The Corvane X2 lasts 20 hours. Here's what else is new",
        """
# The Corvane X2 lasts 20 hours. Here's what else is new

In testing, the Corvane X2's battery lasted 20 hours of continuous video playback,
making it one of the longest-lasting tablets of the year. Corvane revealed the tablet
this week alongside new keyboard accessories.
""",
    ),
    page(
        "https://www.slatereview.net/2025/03/corvane-x2-first-look",
        "Corvane X2 first look",
        """
# Corvane X2 first look

As TechBrief reported, the Corvane X2 delivers 20 hours of video playback on a single
charge. We have not reviewed the X2 yet; our full review will follow.
""",
    ),
]

# --- Cases --------------------------------------------------------------------------
# Each case: (id, pair, group, claim, pages, expected, problem type, origins, rationale)

CASES = [
    # P01: lab measurement vs a personal anecdote repeated as fact
    (
        "S01",
        "P01",
        "supported",
        "In a continuous video-playback test, the Kestrel 7 tablet's battery lasted 20 hours.",
        VOLTREON,
        "true",
        "measurement_original_record",
        "Voltreon Labs report VL-2025-0412 (original test record, on the lab's own site). "
        "gadgetline.news reports that record.",
        "The lab's own report documents the test, the conditions and a 20 h 6 min result.",
    ),
    (
        "U01",
        "P01",
        "unsubstantiated",
        "In a continuous video-playback test, the Pelora Note 5 tablet's battery lasted 22 hours.",
        [
            page(
                "https://www.tabletforum.net/threads/pelora-note-5-battery-is-insane.88213",
                "Pelora Note 5 battery is insane - TabletForum",
                """
# Pelora Note 5 battery is insane

Posted by skyler_k

Just wanted to share: my Pelora Note 5 lasted 22 hours today playing videos nonstop.
Best tablet I've ever owned, honestly.

Reply from mvaughn: nice, mine seems good too.
""",
            ),
            page(
                "https://www.gearwire.co/pelora-note-5-battery-life",
                "Pelora Note 5 battery life: 22 hours of video",
                """
# Pelora Note 5 battery life: 22 hours of video

The Pelora Note 5's battery lasted 22 hours in continuous video playback. That puts it
ahead of most tablets in its class. Pelora has not commented on battery figures.
""",
            ),
            page(
                "https://www.techdigest-daily.com/pelora-note-5",
                "Pelora Note 5 reaches 22 hours of video playback",
                """
# Pelora Note 5 reaches 22 hours of video playback

Users say the Pelora Note 5 runs for 22 hours of continuous video playback, according
to posts on TabletForum and a report by GearWire.
""",
            ),
        ],
        "insufficient_evidence",
        "anecdote_repeated",
        "One forum post by an anonymous user (no method, no conditions). gearwire.co states "
        "it without a source; techdigest-daily.com cites the forum post and gearwire.co.",
        "Every page traces back to one personal anecdote. No recorded test exists.",
    ),
    # P02: the same announcement supports 'advertised' and not 'lasted in a test'
    (
        "S02",
        "P02",
        "supported",
        "Corvane advertised the X2 tablet's battery life as up to 20 hours.",
        CORVANE,
        "true",
        "attribution_publication",
        "Corvane's own press release (original record of what Corvane advertised). Three "
        "other pages paraphrase it.",
        "The claim is about what Corvane advertised; Corvane's own release is that record.",
    ),
    (
        "U02",
        "P02",
        "unsubstantiated",
        "In a continuous video-playback test, the Corvane X2 tablet's battery lasted 20 hours.",
        CORVANE,
        "insufficient_evidence",
        "announcement_paraphrased",
        "All four pages derive from Corvane's 'up to 20 hours' estimate. dailydevice.com "
        "turns it into 'in testing'; slatereview.net cites techbrief.io. No test record.",
        "The same announcement is only the manufacturer's estimate; no one recorded a test.",
    ),
    # P03: benchmark score, maintainer leaderboard vs circular citations
    (
        "S03",
        "P03",
        "supported",
        "The Arvo-3 language model scored 71.4% on the Lumen-QA benchmark.",
        [
            page(
                "https://www.lumenqa.org/leaderboard",
                "Lumen-QA leaderboard",
                """
# Lumen-QA leaderboard

Test set v2.1 (4,000 held-out questions). Last updated 2 October 2025.

All scores below were produced by the Lumen-QA maintainers, who run each submitted
model on the held-out test set themselves. Scores are exact-match accuracy.

| Rank | Model | Organization | Score |
| --- | --- | --- | --- |
| 1 | Arvo-3 | Arvo Research | 71.4% |
| 2 | Tessel-L | Tessel AI | 69.8% |
| 3 | Quarry-2 | Quarry Labs | 66.1% |
""",
            ),
            page(
                "https://www.aipulse.news/arvo-3-tops-lumen-qa",
                "Arvo-3 tops the Lumen-QA leaderboard",
                """
# Arvo-3 tops the Lumen-QA leaderboard

Arvo Research's Arvo-3 now leads Lumen-QA with a score of 71.4%, according to the
benchmark's maintainers, who ran the model on the held-out test set.
""",
            ),
        ],
        "true",
        "benchmark_original_record",
        "Lumen-QA maintainers' leaderboard (they ran the evaluation themselves).",
        "The maintainers' leaderboard is the original record of the score.",
    ),
    (
        "U03",
        "P03",
        "unsubstantiated",
        "The Nimbra-2 language model scored 74.2% on the Lumen-QA benchmark.",
        [
            page(
                "https://www.modelwatch.ai/nimbra-2-lumen-qa",
                "Nimbra-2 hits 74.2% on Lumen-QA",
                """
# Nimbra-2 hits 74.2% on Lumen-QA

Nimbra-2 scored 74.2% on the Lumen-QA benchmark, as first reported by the Neural
Notes blog. That would put it at the top of the benchmark.
""",
            ),
            page(
                "https://www.neuralnotes.blog/2025/10/nimbra-2",
                "Nimbra-2 is here",
                """
# Nimbra-2 is here

Nimbra-2 is out, and it reportedly scored 74.2% on Lumen-QA, according to AI Daily
Brief.
""",
            ),
            page(
                "https://www.aidailybrief.com/nimbra-2-benchmark",
                "Nimbra-2 posts 74.2% on Lumen-QA",
                """
# Nimbra-2 posts 74.2% on Lumen-QA

The Nimbra-2 model scored 74.2% on Lumen-QA, ModelWatch reports.
""",
            ),
        ],
        "insufficient_evidence",
        "circular_citation",
        "modelwatch.ai cites neuralnotes.blog, which cites aidailybrief.com, which cites "
        "modelwatch.ai. No page names who ran the benchmark; no leaderboard or record.",
        "A citation loop with no underlying record.",
    ),
    # P04: official race result vs a repeated unofficial time
    (
        "S04",
        "P04",
        "supported",
        "Ana Ferreira won the 2025 Harrowgate Marathon women's race in 2:24:31.",
        [
            page(
                "https://www.harrowgatemarathon.org/results/2025",
                "2025 official results | Harrowgate Marathon",
                """
# 2025 Harrowgate Marathon: official results

Race date: 12 April 2025. Timing by RaceTime Systems (chip timing). Results ratified
by the race referee on 13 April 2025.

## Women's race: top three

| Place | Name | Club | Chip time |
| --- | --- | --- | --- |
| 1 | Ana Ferreira | Porto Athletics | 2:24:31 |
| 2 | Mira Holt | Leeds City AC | 2:25:58 |
| 3 | Sofia Brandt | TV Hamburg | 2:27:12 |
""",
            ),
            page(
                "https://www.harrowgateherald.co.uk/sport/ferreira-wins-marathon",
                "Ferreira wins Harrowgate Marathon",
                """
# Ferreira wins Harrowgate Marathon

Portugal's Ana Ferreira won the women's race at the Harrowgate Marathon on Saturday
in 2:24:31, according to the official results.
""",
            ),
        ],
        "true",
        "official_result",
        "The race organiser's official, ratified results page.",
        "The organiser's ratified results are the original record of the time.",
    ),
    (
        "U04",
        "P04",
        "unsubstantiated",
        "Tomas Lind won the 2025 Saltmere Marathon men's race in 2:09:47.",
        [
            page(
                "https://www.runnerscorner.blog/saltmere-2025",
                "Saltmere 2025: Lind takes it",
                """
# Saltmere 2025: Lind takes it

Tomas Lind won the Saltmere Marathon men's race in 2:09:47! What a run from the
Swede.
""",
            ),
            page(
                "https://www.marathonhub.net/news/lind-saltmere",
                "Lind wins Saltmere Marathon in 2:09:47",
                """
# Lind wins Saltmere Marathon in 2:09:47

Sweden's Tomas Lind won the 2025 Saltmere Marathon men's race in 2:09:47. Times are
unofficial and based on reports from the course.
""",
            ),
            page(
                "https://www.sportsroundup.com/athletics/saltmere-marathon",
                "Saltmere Marathon: Lind wins men's race",
                """
# Saltmere Marathon: Lind wins men's race

Tomas Lind crossed the line first in the Saltmere Marathon men's race, clocking
2:09:47, according to MarathonHub.
""",
            ),
        ],
        "insufficient_evidence",
        "repeated_unofficial_result",
        "runnerscorner.blog states it without a source; marathonhub.net says the time is "
        "unofficial; sportsroundup.com cites marathonhub.net. No official results page.",
        "Repeated unofficial time; the organiser's record is absent.",
    ),
    # P05: what an organization published vs a spokesperson quote about it
    (
        "S05",
        "P05",
        "supported",
        "The Orlen Valley Water Authority's 2025 annual report states that it treated "
        "41.2 billion litres of water.",
        [
            page(
                "https://www.orlenvalleywater.gov/about/annual-report-2025",
                "Annual Report 2025 | Orlen Valley Water Authority",
                """
# Annual Report 2025

Orlen Valley Water Authority · Published 30 June 2025

## Operations

In fiscal year 2025 the Authority treated 41.2 billion litres of water at its three
treatment works, up from 39.8 billion litres in 2024. Average daily demand was 113
million litres.
""",
            ),
        ],
        "true",
        "attribution_publication",
        "The authority's own annual report page.",
        "The claim is about what the report states, and the report itself is in the packet.",
    ),
    (
        "U05",
        "P05",
        "unsubstantiated",
        "The Merrow Basin Water Board's 2025 annual report states that it treated "
        "38.6 billion litres of water.",
        [
            page(
                "https://www.merrowgazette.co.uk/news/water-board-usage",
                "Water board says demand rose last year",
                """
# Water board says demand rose last year

The Merrow Basin Water Board treated about 38.6 billion litres of water last year, a
spokesperson told the Gazette. Demand rose during the dry summer, the spokesperson
said.
""",
            ),
            page(
                "https://www.basinnews.com/merrow-water-38-billion",
                "Merrow Basin Water Board treated 38.6 billion litres",
                """
# Merrow Basin Water Board treated 38.6 billion litres

The Merrow Basin Water Board treated 38.6 billion litres of water in 2025, the
Merrow Gazette reported.
""",
            ),
        ],
        "insufficient_evidence",
        "attribution_without_record",
        "A spokesperson's remark to merrowgazette.co.uk; basinnews.com cites the Gazette. "
        "The annual report is not in the packet and no page quotes it.",
        "The claim is about the report's contents; no page shows what the report states.",
    ),
    # P06: surveyed elevation (real) vs a personal GPS reading repeated as fact
    (
        "S06",
        "P06",
        "supported",
        "Denali, the highest point in Alaska, has an elevation of 20,320 feet, according "
        "to the U.S. Geological Survey.",
        [saved("c-09", "highest-and-lowest")],
        "true",
        "attribution_publication_real",
        "USGS 'Highest and Lowest Elevations' table on usgs.gov (real page, saved Nov 16).",
        "The USGS page itself lists Denali at 20,320 feet.",
    ),
    (
        "U06",
        "P06",
        "unsubstantiated",
        "Mount Arvid, the highest point in Tessaly County, has an elevation of 8,214 feet, "
        "according to the Tessaly County Survey Office.",
        [
            page(
                "https://www.summitlog.blog/2025/07/mount-arvid",
                "Mount Arvid: county high point bagged",
                """
# Mount Arvid: county high point bagged

Made it up Mount Arvid today, the highest point in Tessaly County. My GPS watch read
8,214 feet at the top. Great views over the valley.
""",
            ),
            page(
                "https://www.trailfinder.net/peaks/mount-arvid",
                "Mount Arvid (8,214 ft) | TrailFinder",
                """
# Mount Arvid (8,214 ft)

Mount Arvid is the highest point in Tessaly County, with an elevation of 8,214 feet
according to the Tessaly County Survey Office. The trail is 6.2 miles each way.
""",
            ),
        ],
        "insufficient_evidence",
        "anecdote_misattributed",
        "One hiker's GPS reading (summitlog.blog). trailfinder.net attributes the same "
        "figure to the survey office without citing any survey record.",
        "A personal reading, then attributed to an office whose record is not shown.",
    ),
    # P07: WHO estimate (real) vs an estimate of unknown origin
    (
        "S07",
        "P07",
        "supported",
        "The World Health Organization estimated that 610,000 people died of malaria "
        "worldwide in 2024.",
        [saved("a-10", "who.int/data/gho")],
        "true",
        "attribution_publication_real",
        "WHO Global Health Observatory malaria page on who.int (real page, saved Nov 16).",
        "WHO's own page states the 2024 estimate of 610 000 deaths.",
    ),
    (
        "U07",
        "P07",
        "unsubstantiated",
        "The Ostrava Institute for Tropical Health estimated that 47,000 people died of "
        "dengue worldwide in 2024.",
        [
            page(
                "https://www.healthwirenow.com/dengue-deaths-2024",
                "Dengue deaths reached 47,000 in 2024",
                """
# Dengue deaths reached 47,000 in 2024

An estimated 47,000 people died of dengue worldwide in 2024, the Ostrava Institute for
Tropical Health said, according to a post shared widely on social media.
""",
            ),
            page(
                "https://www.globalhealthbrief.org/dengue-2024",
                "Ostrava Institute: 47,000 dengue deaths in 2024",
                """
# Ostrava Institute: 47,000 dengue deaths in 2024

The Ostrava Institute for Tropical Health estimates that 47,000 people died of dengue
in 2024, HealthWire Now reported.
""",
            ),
        ],
        "insufficient_evidence",
        "unknown_origin",
        "healthwirenow.com relays an unidentified social-media post; globalhealthbrief.org "
        "cites healthwirenow.com. No institute publication is shown.",
        "The only origin is an unattributed social post.",
    ),
    # P08: official launch record (real) vs one unattributed page
    (
        "S08",
        "P08",
        "supported",
        "NASA's SpaceX Crew-11 mission launched from Launch Complex 39A at Kennedy Space "
        "Center at 11:43 a.m. EDT.",
        [saved("a-13", "crew-11-launches")],
        "true",
        "official_record_real",
        "NASA's own news release on nasa.gov (real page, saved Nov 16).",
        "NASA's release records the launch time and pad.",
    ),
    (
        "U08",
        "P08",
        "unsubstantiated",
        "The Halcyon-4 crewed mission launched from Pad 2 at Varnholm Spaceport at 9:17 a.m. "
        "local time.",
        [
            page(
                "https://www.orbitfans.net/halcyon-4-launch",
                "Halcyon-4 is on its way",
                """
# Halcyon-4 is on its way

The Halcyon-4 crewed mission launched from Pad 2 at Varnholm Spaceport at 9:17 a.m.
local time. Three astronauts are aboard for a ten-day flight.
""",
            ),
        ],
        "insufficient_evidence",
        "bare_assertion",
        "One fan site states it with no source. The operator's or spaceport's record is absent.",
        "A single bare assertion with no record behind it.",
    ),
    # P09: owner's own page vs planted casual mentions ("the dog is blue")
    (
        "S09",
        "P09",
        "supported",
        "Biscuit, the mascot dog of Ashcombe Town Football Club, is a golden retriever.",
        [
            page(
                "https://www.ashcombetownfc.co.uk/club/meet-biscuit",
                "Meet Biscuit | Ashcombe Town FC",
                """
# Meet Biscuit, our club mascot

Biscuit is Ashcombe Town Football Club's mascot dog. She is a five-year-old golden
retriever who joined the club in 2021 and leads the team out at every home game.
""",
            ),
        ],
        "true",
        "owner_record",
        "The club's own page about its mascot.",
        "The owner's own page is the original record of the dog's breed.",
    ),
    (
        "U09",
        "P09",
        "unsubstantiated",
        "Pebble, the mascot dog of Fenwick Rangers Football Club, has a blue coat.",
        [
            page(
                "https://www.terracechat.net/fenwick-rangers-matchday",
                "Fenwick Rangers matchday notes",
                """
# Fenwick Rangers matchday notes

Good crowd on Saturday, and Pebble, Fenwick Rangers' blue-coated mascot dog, got the
biggest cheer of the day.
""",
            ),
            page(
                "https://www.groundhopperdiary.com/fenwick",
                "Groundhopping: Fenwick Rangers",
                """
# Groundhopping: Fenwick Rangers

Pies were decent. The highlight was Pebble, the club's mascot dog, who has a blue
coat.
""",
            ),
            page(
                "https://www.nonleaguefacts.org/fenwick-rangers",
                "Fenwick Rangers: ten facts",
                """
# Fenwick Rangers: ten facts

7. The club's mascot is Pebble, a dog with a blue coat.
""",
            ),
        ],
        "insufficient_evidence",
        "planted_mentions",
        "Three pages on unrelated sites mention it in passing, with no source; written for "
        "this set as planted pages. The club's own record is absent.",
        "Planted casual mentions; no owner record or observation.",
    ),
    # P10: a lab's own report vs copies of a 'lab report' on unrelated domains
    (
        "S10",
        "P10",
        "supported",
        "Ternwell Audio Lab measured the Quill E4 earbuds' battery life at 9.5 hours.",
        [
            page(
                "https://www.ternwellaudiolab.com/tests/quill-e4",
                "Quill E4 battery test | Ternwell Audio Lab",
                """
# Quill E4 battery test

Ternwell Audio Lab · Test TAL-2025-118 · 9 September 2025

Method: two Quill E4 pairs, fully charged, played a pink-noise track at 75 dB with
noise cancelling on, until the first earbud shut off.

Result: Ternwell Audio Lab measured the Quill E4's battery life at 9.5 hours (9 h 31
min average across both pairs).
""",
            ),
        ],
        "true",
        "measurement_original_record",
        "The lab's own test page on its own domain.",
        "The lab's report documents method, conditions and result.",
    ),
    (
        "U10",
        "P10",
        "unsubstantiated",
        "Lumora Labs measured the Vexa S2 earbuds' battery life at 11 hours.",
        [
            page(
                "https://www.bestearbudsdeals.net/vexa-s2-lab-report",
                "Lumora Labs test report: Vexa S2",
                """
# Lumora Labs test report: Vexa S2

Test LL-2025-77. Method: pink noise at 75 dB, noise cancelling on, until shut-off.

Result: Lumora Labs measured the Vexa S2's battery life at 11 hours.

Buy the Vexa S2 now with 30% off using code VEXA30.
""",
            ),
            page(
                "https://www.vexa-review-hub.com/lumora-test",
                "Lumora Labs test report: Vexa S2",
                """
# Lumora Labs test report: Vexa S2

Test LL-2025-77. Method: pink noise at 75 dB, noise cancelling on, until shut-off.

Result: Lumora Labs measured the Vexa S2's battery life at 11 hours.
""",
            ),
            page(
                "https://www.gadgetbargainz.co/vexa-s2",
                "Vexa S2: lab-tested 11-hour battery",
                """
# Vexa S2: lab-tested 11-hour battery

Lumora Labs test report, test LL-2025-77: Lumora Labs measured the Vexa S2's battery
life at 11 hours. Shop the Vexa S2 today.
""",
            ),
        ],
        "insufficient_evidence",
        "fabricated_record",
        "One copy-pasted text presented as a Lumora Labs report on three retail/affiliate "
        "domains unrelated to Lumora Labs. Written for this set as a forgery.",
        "A 'lab report' that appears only on sites the lab does not own; one origin.",
    ),
]

# Two extra cases, reported separately from the 20: a test-conditions mismatch, and a
# contradiction that must stay False.
EXTRA = [
    (
        "X01",
        "extra",
        "unsubstantiated",
        "In a continuous web-browsing test, the Kestrel 7 tablet's battery lasted 20 hours.",
        VOLTREON,
        "insufficient_evidence",
        "conditions_mismatch",
        "Voltreon's report covers video playback only and says no browsing test was run.",
        "The record is for a different test; it neither supports nor contradicts browsing.",
    ),
    (
        "X02",
        "extra",
        "contradicted",
        "In a continuous video-playback test, the Kestrel 7 tablet's battery lasted 24 hours.",
        VOLTREON,
        "false",
        "contradicted_by_record",
        "Voltreon's report records 20 h 6 min in that exact test.",
        "The original record states a different result for the same test.",
    ),
]


def build():
    packets, answers = [], []
    for row in CASES + EXTRA:
        cid, pair, group, claim, pages, expected, kind, origins, rationale = row
        packets.append({"id": cid, "claim": claim, "pages": pages})
        answers.append(
            {
                "id": cid,
                "pair": pair,
                "group": group,
                "expected": expected,
                "problem_type": kind,
                "known_origins": origins,
                "rationale": rationale,
            }
        )
    core = [a for a in answers if a["pair"] != "extra"]
    assert len(core) == 20
    assert sum(a["group"] == "supported" for a in core) == 10
    blob = json.dumps(packets, indent=1, ensure_ascii=False) + "\n"
    (HERE / "packets.json").write_text(blob)
    (HERE / "answers.json").write_text(json.dumps(answers, indent=1, ensure_ascii=False) + "\n")
    digest = hashlib.sha256(blob.encode()).hexdigest()
    (HERE / "packets.sha256").write_text(digest + "  packets.json\n")
    print(digest)


if __name__ == "__main__":
    build()
