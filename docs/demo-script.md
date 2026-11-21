# Demo video script

A video of 3 minutes or less for the ODSC × Nebius submission. There is no live demo day:
judges score this video and the repository. It is recorded as **6 clips of at most 30
seconds each**, with a voiceover, and edited into one video afterwards. Aim for about 25 s
per clip, so the video lands near 2:45.

| Criterion | Weight | Shown in |
| --- | ---: | --- |
| Sourced and verifiable answers | 30% | Clip 3: the highlighted quotation opens on its source page; Clip 6: no guess when the pages don't say |
| Works end to end | 25% | Clips 2, 5 and 6: real live runs through the web client and API |
| Usefulness | 20% | Clips 1 and 2: a health reporter checking a figure before it is published |
| Agent design | 15% | Clip 4: the research log and quotation checks; Python in control |
| Use of Token Factory and Tavily | 10% | Clips 2 and 4: the log names every call |

## Before recording

- **Fresh history:** restart the API on a new `ALETHEIA_DATABASE_PATH` file (for example
  `data/demo2.sqlite3`), so rehearsal claims don't show under Recent investigations in
  Clip 6. Never show `.env` or a terminal that prints it.
- **Browser:** full screen (F11), at a zoom where the report fits without scrolling. The
  app is always dark.
- **Each clip:** start recording, wait 1 s, speak, wait 1 s, stop. Name the files
  `clip-1.mp4` … `clip-6.mp4`.
- **Waiting for results:** runs take 15–50 s. Keep talking over the first seconds of the
  research log, then pause the recording until the answer appears; the wait is cut in
  editing.
- **If an answer comes out differently on the day,** use it as it is, or swap in a spare
  claim. Never edit a result. Answers can vary between runs: on the 77 trusted claims, two
  DeepSeek runs differed on 13. The three claims below were right in both.

## Clip 1 · What Aletheia is

**Screen:** the home page, search box empty. Keep the mouse still.

**Say:**

> This is Aletheia, a research agent that brings its sources.
> You give it a claim, the way you remember it, or the way a draft states it.
> It searches the live web, reads the pages, and tells you whether the claim is true,
> false, or can't be settled.
> And every answer comes with the exact passages it rests on, so you can check it yourself.

**Last action:** move the mouse to the search box.

## Clip 2 · A live check

**Screen:** the home page.

1. Click the search box and type
   `An estimated 610,000 people died of malaria worldwide in 2024, according to WHO.`

   > Say you're a health reporter, and your draft says 610,000 people died of malaria in
   > 2024. Let's check it, live.

2. Click **Verify**.
3. As the log fills in, point at a "Token Factory model call" line, then a "Tavily search"
   line.

   > A model on Nebius Token Factory plans the searches.
   > Tavily runs them in parallel and reads the best pages.
   > Then the model gives a verdict, with quotations copied word for word from those pages.

**Stop** once you've finished speaking. Resume recording when the answer appears: that is
the start of Clip 3.

## Clip 3 · The answer, and its source

**Screen:** the finished report: **True**.

1. Pause on the verdict and the explanation.

   > True.

2. Move to the **Evidence** card and its highlighted quotation.

   > Here's the quotation it relied on, highlighted.

3. Click **Link to source**. The page opens at that sentence; hold for 3 s.

   > Click Link to source, and the original page opens at that exact sentence.

4. Switch back to the Aletheia tab.

   > You don't have to trust the verdict. You can check it in one click, and cite it.

## Clip 4 · How the agent works

**Screen:** the same report.

1. Click **Pages Read** in the Investigation Audit Trail.

   > Below that is the audit trail. Pages Read lists every page it opened, not just the
   > ones it quoted.

2. Click **Research log**. Point at a Token Factory line, then a Tavily line.

   > The research log shows every step: each Token Factory call and each Tavily search.

3. Keep the log on screen.

   > Python stays in control throughout. It runs the searches, enforces the limits, and
   > checks every quotation against the saved page.
   > A quotation that isn't there is thrown out.

## Clip 5 · A figure that's close, but wrong

**Screen:** the same report.

1. Click **← Check another claim**, then type
   `The WHO African Region accounted for 75% of global malaria cases in 2024.`

   > Now a figure that's close, but wrong.

2. Click **Verify**. Pause the recording until the answer appears.
3. The answer: **False**. Point at the Evidence card's quotation.

   > False.
   > The quotation shows the share the source actually reports, so the writer can correct
   > the sentence instead of guessing.

## Clip 6 · When it can't tell, and the close

**Screen:** the False report.

1. Click **← Check another claim**, then type
   `Exactly 87 hikers reached Mount Whitney's California summit on July 1, 2001.`

   > And when the web doesn't have the answer?

2. Click **Verify**. Pause the recording until the answer appears.
3. The answer: **Insufficient evidence**. Point at the note under the explanation.

   > Insufficient evidence. The pages it found don't give a summit count for that day, so
   > it doesn't guess.

4. Click **← Check another claim**. Your three checks are listed under **Recent
   investigations**.

   > Every check is saved.
   > On 77 claims with checked answers, it got 66 right in two separate live runs.

5. Hold for 2 s.

   > Aletheia: evidence first.

## Spare claims

Also right in both DeepSeek runs on the 77, each under 45 s unless noted:

| Expected | Claim |
| --- | --- |
| True | IMAP launched for NASA from Kennedy Space Center in Florida on September 24, 2025. |
| True | The Milano Cortina 2026 Winter Olympics in Italy included 116 medal events. |
| False | A New Glenn rocket carried NASA's IMAP from Florida on September 24, 2025. |
| False | WHO placed the worldwide number of new malaria cases in 2015 at 273 million. |
| Insufficient evidence | Exactly 6,324 visitors watched the September 24, 2025, IMAP launch from Kennedy Space Center in Florida. (45–51 s) |

## After recording

- Join the clips in order, cut the waits, and check the length is 3:00 or less.
- Check that every result on screen is a real, unedited run.
- Add the video link to the top of the README and to the submission form.
