# Proposed Step 7 claims

Prepared on November 5, 2026. These are AI proposals, not human-reviewed labels. All 20 are tuning cases; none is held out. The reference pages were checked with built-in web search independently of the application’s Tavily research.

The two Almost cases and both conflict cases particularly need human judgment. A human may reject or re-scope a proposal; preserve its original ID and explain the change. Do not change labels solely to match observed model results.

| ID | Type | Claim | Proposed outcome | Reference |
| --- | --- | --- | --- | --- |
| t001 | direct_fact | Apollo 11 landed on the Moon on July 20, 1969. | true | [Source 1](https://www.nasa.gov/wp-content/uploads/static/history/SP-4029/Apollo_11a_Summary.htm) |
| t002 | direct_fact | Marie Curie won the Nobel Prize in Chemistry in 1903. | false | [Source 1](https://www.nobelprize.org/nomination/archive/show_people.php?id=2051&lang=en) |
| t003 | direct_fact | Tim Berners-Lee invented the World Wide Web at CERN in 1989. | true | [Source 1](https://home.cern/science/computing/the-birth-of-the-web) |
| t004 | direct_fact | The James Webb Space Telescope launched on December 25, 2021. | true | [Source 1](https://svs.gsfc.nasa.gov/14060) |
| t005 | direct_fact | Albert Einstein’s 1921 Nobel Prize in Physics was awarded specifically for his theory of relativity. | false | [Source 1](https://www.nobelprize.org/prizes/physics/1921/ceremony-speech/) |
| t006 | comparison | Mercury is hotter on average at its surface than Venus. | false | [Source 1](https://science.nasa.gov/mercury/facts/), [Source 2](https://science.nasa.gov/venus/venus-facts/) |
| t007 | causal | Venus’s dense atmosphere makes its surface hotter through a greenhouse effect. | true | [Source 1](https://science.nasa.gov/venus/venus-facts/), [Source 2](https://science.nasa.gov/mercury/facts/) |
| t008 | causal | Northern Hemisphere summer is primarily caused by Earth being closer to the Sun. | false | [Source 1](https://aa.usno.navy.mil/faq/seasons_orbit), [Source 2](https://www.weather.gov/fsd/season) |
| t009 | causal | Earth’s axial tilt is the primary cause of its annual seasons. | true | [Source 1](https://aa.usno.navy.mil/faq/seasons_orbit), [Source 2](https://www.weather.gov/fsd/season) |
| t010 | causal | At higher elevations, lower atmospheric pressure makes water boil at a lower temperature. | true | [Source 1](https://extension.colostate.edu/resource/high-elevation-food-preparation-guide/) |
| t011 | comparison | Mount Everest is Earth’s highest mountain measured above mean sea level. | true | [Source 1](https://oceanservice.noaa.gov/facts/highestpoint.html) |
| t012 | comparison | Mount Everest’s summit is the point on Earth’s surface farthest from Earth’s center. | false | [Source 1](https://oceanservice.noaa.gov/facts/highestpoint.html), [Source 2](https://blogs.loc.gov/maps/2020/11/extremities-of-the-earth-farthest-point-from-the-center-of-the-earth/) |
| t013 | comparison | Chimborazo’s summit is farther from Earth’s center than Mount Everest’s summit. | true | [Source 1](https://oceanservice.noaa.gov/facts/highestpoint.html), [Source 2](https://blogs.loc.gov/maps/2020/11/extremities-of-the-earth-farthest-point-from-the-center-of-the-earth/) |
| t014 | interpretive | Antarctica is a desert because it receives very little precipitation. | true | [Source 1](https://www.bas.ac.uk/about/education-and-schools/antarctic-factsheet/) |
| t015 | interpretive | A light-year is a unit of time. | false | [Source 1](https://science.nasa.gov/exoplanets/what-is-a-light-year/) |
| t016 | direct_fact | American scientist Tim Berners-Lee invented the World Wide Web at CERN in 1989. | almost | [Source 1](https://home.cern/science/computing/the-birth-of-the-web) |
| t017 | direct_fact | The James Webb Space Telescope was launched successfully in December 2021 aboard an Ariane 4 rocket. | almost | [Source 1](https://svs.gsfc.nasa.gov/14060) |
| t018 | conflict | The present-day cosmic expansion rate is approximately 73 kilometers per second per megaparsec. | conflicting_evidence | [Source 1](https://science.nasa.gov/mission/hubble/science/science-behind-the-discoveries/hubble-constant-and-tension/) |
| t019 | conflict | Phosphine gas was present in Venus’s clouds during the observations reported by Greaves and colleagues in 2020. | conflicting_evidence | [Source 1](https://arxiv.org/abs/2009.06593), [Source 2](https://arxiv.org/abs/2010.14305) |
| t020 | insufficient | The 1977 Wow! radio signal was produced by an extraterrestrial civilization. | insufficient_evidence | [Source 1](https://www.seti.org/research/seti-101/the-wow-signal), [Source 2](https://seti.berkeley.edu/wow/) |

## Review workflow

Use the JSON companion for scope, proposed corrections, flag expectations, and reference notes. The reference URLs are evaluator-only; the runner sends only the claim and its stated context to the application.

1. Two human labelers should independently assess the claims and sources before seeing the application’s results. Because this proposal includes suggested answers, anyone who has read them should disclose that exposure; do not claim a blind agreement rate from those reviews.
2. Resolve disagreements explicitly, especially whether the secondary detail makes a claim Almost or materially False. A correct True claim may still carry a comparison flag.
3. Use PR #7’s label files and reconciled format when that work is merged. This proposal is deliberately outside `evals/claims.json` and has `status: proposed`, with no invented labelers.
4. Keep Pari’s six held-out cases outside the repository and away from prompt authors until the final evaluation. This proposed set does not fulfill that held-out requirement.
5. Review each explanation and correction against the cited source passages. An agent’s check does not count as human review.

The set currently emphasizes science/history facts and contains only one expected flag. It is a starting proposal, not representative evidence of performance on AI benchmark comparisons, healthcare, or other domains. Add independently reviewed flag cases before claiming flag detection quality.
