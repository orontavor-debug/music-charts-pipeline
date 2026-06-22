# Presentation Notes — Music Charts Pipeline

This file is a running log of decisions made, hurdles encountered, and the reasoning
behind technical choices. Updated every session. Use it to build your final presentation.

---

## What this project is (one sentence)

An automated data pipeline that fetches daily music chart data from the Last.fm API —
globally and for 5 countries — enriches it with genre (Last.fm tags) and artist metadata
(MusicBrainz: origin country, type, gender, formation year), stores it in the cloud (AWS S3),
loads it into a local Postgres warehouse, models it as a star schema with dbt, and
displays trend KPIs in a Metabase dashboard.

---

## The tech stack and why each tool was chosen

| Tool | Role | Why chosen |
|---|---|---|
| Python + pandas | Fetch, clean, combine data | Industry standard for data engineering |
| Last.fm API | Music chart data + genre tags | Free, no OAuth, verified working |
| MusicBrainz API | Artist metadata (origin, type, gender, year) | Free, open music database, joined via artist MBID |
| AWS S3 | Cloud storage | Near-free, standard DE tool |
| AWS Glue | Runs Python in the cloud | Real DE service, matches school examples |
| AWS Step Functions | Orchestration | Runs jobs in order with retries |
| AWS Lambda + SNS | Notifications | Success/failure alerts |
| PostgreSQL (local) | Warehouse | Free forever — Snowflake trial only 30 days |
| dbt | SQL transformations, star schema | Industry standard modeling tool |
| GitHub Actions | CI/CD | Auto-runs dbt tests on push |
| Metabase | Dashboard | Free, runs locally via Docker |

---

## Key design decisions

### Why local Postgres instead of Snowflake?
Snowflake's free trial is 30 days. The project runs for 4 weeks, so the trial would
expire before the submission date. Postgres is free forever and already installed.
All the AWS cloud pieces (Glue, S3, Step Functions) are kept so the project still
demonstrates cloud ingestion — only the warehouse is local.
Portfolio line: "warehouse-agnostic dbt project — runs on local Postgres or Snowflake
by switching the connection profile."

### Why split into src/lastfm.py and pipeline.py?
`lastfm.py` handles all API communication (the "phone").
`pipeline.py` handles all data logic (the "brain").
Reason: the retry/timeout/pause logic is reusable across all three endpoints.
Keeping them separate means each file has one clear responsibility.

### Why fetch country charts separately from the global chart?
Two different API endpoints with different fields:
- `chart.getTopTracks` = global, no rank returned, has listeners
- `geo.getTopTracks` = per country, rank returned, no listeners
They also cover different time windows: global is "right now", country is "last week".
This is documented as a known difference, not a bug.

### Why derive global rank from list position?
The global endpoint doesn't return a rank number. Last.fm returns tracks in popularity
order (most popular first), so we assign rank 1 to the first item, rank 2 to the second,
etc. using Python's enumerate(). This is an assumption based on API behavior.

### Why 300 rows per daily snapshot?
1 global chart × 50 tracks = 50 rows
5 country charts × 50 tracks = 250 rows
Total = 300 rows
The same track can appear multiple times (once per chart it's on). Each row = one track
on one chart on one day. This is intentional — it's what allows cross-country comparison.

### Genre coverage limitation — known and documented
~42% of rows have genre="unknown". This is NOT a bug. Investigation showed 80% of
unknown-genre tracks have zero tags at all on Last.fm — the remaining 20% have junk
tags (usernames, personal labels). The gap is concentrated in country charts for
non-English-speaking markets (Japan, Germany, Brazil) where Last.fm's crowd-sourced
tags are sparse. Presentation line: "Genre coverage is 58% — the gap is in country
charts for non-Western markets, a known limitation of crowd-sourced tagging."

### Why a KNOWN_GENRES allowlist for genre picking?
Last.fm has no genre field. It returns crowd-sourced "tags" which are messy — usernames,
personal labels ("seen live", "favorites"), non-genre words. We maintain a list of real
genre names and pick the first tag that matches. If none match, default to "unknown".
"unknown" is an intentional, documented fallback — not a bug.

### Why add MusicBrainz as a second data source?
Last.fm tells us what tracks are charting and where. MusicBrainz tells us where those
artists are FROM. Combining the two unlocks a genuinely interesting question: which
countries produce charting artists vs which countries consume them? Is Japan's chart
dominated by local artists? Are Korean acts (like BTS) disproportionately popular outside
Korea? This "origin vs consumption" angle is not possible with Last.fm data alone.
Join key: artist MBID (present in 97% of Last.fm rows). Clean join — no fuzzy matching.
MusicBrainz fields used: country of origin, artist type (person vs group),
formation year, gender. All verified with 100% coverage in a pre-build sample check
(gender is 73% — missing only for bands, which is correct behavior).

### dbt tests: built-in only
Decision: use only the 4 built-in dbt tests (not_null, unique, accepted_values,
relationships). These are YAML config — no SQL needed. Easy to explain in interviews.
Custom tests are out of scope unless ahead of schedule.

### rank_change: LAG() window function, sign convention
fact_chart_entry_trends joins fact_chart_entry to dim_date (needed because date_key is
an md5 hash and doesn't sort chronologically — only the real snapshot_date does), then
uses `LAG(rank) OVER (PARTITION BY track_key, country_key ORDER BY snapshot_date)` to
pull each track's rank from its previous appearance in that same chart.
`rank_change = previous_rank - rank` — climbing the chart (e.g. rank 5 -> rank 2) gives
a positive number (5 - 2 = +3), falling gives negative. This makes "biggest movers" a
plain `ORDER BY rank_change DESC`. A track's first-ever appearance in a chart has
previous_rank = NULL and therefore rank_change = NULL — expected, not a bug (nothing to
compare against yet).

### Why use dbt at all, if the data already lives in Postgres?
Common point of confusion, worth having a clean answer for in interviews: dbt is not a
database and stores nothing. It only generates and runs SQL against Postgres (CREATE
TABLE AS SELECT for each model, SELECT COUNT(*) checks for each test), then gets out of
the way. Once `dbt run` finishes, the resulting tables sit in Postgres like any other
table — Metabase, pgAdmin, psql, anything that speaks SQL queries them directly with
zero dbt involvement. What dbt actually buys us: (1) dependency ordering — it knows
fact_chart_entry depends on the dimensions which depend on staging, and builds in the
right order automatically; (2) reusable references via ref() instead of copy-pasted SQL;
(3) a built-in test framework (not_null/unique/relationships) instead of hand-written
QA queries; (4) auto-generated lineage documentation (dbt docs); (5) every model is a
version-controlled .sql file, so the transformation logic has real git history.

### Why chain dbt into the daily load (run_daily_pipeline.sh)
Realized a second gap behind the duplicate-key bug above: even on a day the cron job DID fire
successfully, it only loaded raw rows into Postgres — it never re-ran dbt. So a bad day's data
(like the Justin Bieber gap) could sit silently in `raw_chart_entries`, completely untested,
until someone happened to run `dbt run && dbt test` by hand. The tests we built are only useful
if they actually run. Fix: `run_daily_pipeline.sh` — one script doing load -> dbt run -> dbt test
as a single chain, called identically by the daily cron job (no argument = load today) and by
manual backfills (one argument = a specific past date). Either path now always ends with all 24
dbt tests running against the freshest data. This is deliberately a different safety net from
Phase 6 (GitHub Actions running dbt tests on push): GitHub Actions catches bugs in the SQL/model
*code* when it changes; this catches bad *data* the moment it arrives, regardless of whether the
code changed at all. Both matter, for different failure modes — one isn't a substitute for the other.

### Why a single fact table grain works for most KPIs
Checked all 5 planned KPIs against fact_chart_entry / fact_chart_entry_trends before
starting Metabase work. 4 of 5 (top tracks now, genre breakdown by country, trend over
time, biggest movers) are answerable directly with a filter + GROUP BY against the
existing tables — a sign the fact grain ("one row per track, per chart, per day") was
the right choice. The exception is "global vs country" (comparing a track's global rank
to its rank in a specific country chart, same day) — that's not an aggregation, it's a
comparison between two specific rows, which needs a self-join. Decided to design that
as its own small dbt model once we're in Metabase and know the exact shape the chart
needs, rather than guessing ahead of time.

### A UX "fix" that backfired — flipping the rank axis on the trend chart
Built KPI 4 (trend over time) as a line chart: X-axis = snapshot date, Y-axis = Rank,
one line per track. Noticed the Y-axis reads against intuition — rank 1 (best) sits at
the bottom, rank 10 (worst) at the top, so a line moving "up" is actually getting worse.
Tried the obvious fix: a custom column `51 - Rank` ("Chart Score"), so climbing the
chart moves the line up, matching normal trend-chart intuition. This backfired: once
the chart was filtered to only the top 5 ranks, the transformed values only span a
4-point range (46-50) crammed near the top of an implied 0-50 scale — all the actual
movement got visually flattened, hiding the line crossings that were the whole point of
the chart. Reverted to raw Rank, which auto-scales to its small natural range (1-5) and
shows the crossings clearly. **Lesson, good for a presentation soundbite:** a UX
improvement that's correct in the abstract can actively hurt readability once you've
already narrowed the data — chose to keep the "technically backwards" axis and add a
one-sentence verbal caveat ("lower rank = better") instead of distorting the data to fix
a problem that, in this specific narrowed view, didn't actually exist.

### Why KPI 5 (biggest movers) needed raw SQL instead of the GUI query builder
KPI 5's design goal was a diverging bar chart showing the biggest CLIMBERS and biggest
FALLERS together (like a stock market gainers/losers board), not just a one-directional
top-N list. Metabase's visual query builder can only sort + limit a single result set in
one direction per question (e.g. "top 5 by rank_change DESC" OR "bottom 5", not both at
once). Solution: hand-write a native SQL question — two near-identical SELECTs (one
`ORDER BY rank_change DESC LIMIT 5`, one `ORDER BY rank_change ASC LIMIT 5`) combined
with `UNION ALL`, each tagged with a `direction` column ('climber'/'faller') used for
color-coding the bars. Used `WHERE snapshot_date = (SELECT MAX(snapshot_date) ...)`
instead of hardcoding a date, so the question keeps working correctly as more days
accumulate. Tested directly in psql before pasting into Metabase, to separate "is the
SQL logic correct" from "is Metabase configured correctly" — confirmed real, varied
results (Tame Impala/LE SSERAFIM/Zara Larsson/sombr/The Killers climbing; Ariana Grande/
Arctic Monkeys/Taylor Swift/Clairo falling), notably more diverse than KPI 1/4, which
are currently dominated by a single album release. Worth knowing for interviews: this is
a clean example of knowing when to drop from a GUI tool down to raw SQL — not because
the GUI is bad, but because some queries (here, "top N from both ends of a sort")
genuinely need a UNION, which visual query builders generally can't express.

### KPI 2 (global vs country): a self-join, and sorting for the interesting story
This was the project's first SELF-JOIN: `fact_chart_entry` joined to itself, matched on
`track_key` + `date_key` (same track, same day), with one side filtered to
`chart_scope = 'global'` and the other to `chart_scope != 'global'`. Conceptually this
answers "find the same track's row on two different charts on the same day" — a
different shape of question from every other model in the project (which all join
DIFFERENT tables together; this joins one table to itself to compare two of its own rows).

The first version of this query sorted by global rank ascending (i.e. "show the country
ranks of the top global tracks") — but since the global chart is currently dominated by
one album (see KPI 1's Olivia Rodrigo note), that just repeated the same story a third
time. **Changed the sort to `ORDER BY global_rank - country_rank DESC`** instead — this
surfaces the BIGGEST gaps between a track's global and country rank, which produced a
genuinely different and more interesting result: tracks that are barely-charting
worldwide but quietly huge in one specific market (e.g. Malcolm Todd — "Sweet Boy",
ranked #50 globally but #21 in the United States; The Killers' "Mr. Brightside" ranked
#28 globally but #8 in Germany, presumably an older song still loved there specifically).
**Presentation line:** "The interesting data wasn't in the obvious sort order — once I
sorted for the outliers instead of the leaders, the dashboard told a completely
different and more useful story." Good example of analysis, not just querying — the
SQL syntax was easy; choosing what to ask for was the actual work.

Mathematically worth noting: top-ranked global tracks can never show a large gap here,
since their global rank is already near 1 and the gap is bounded by how much room is
above them — a useful thing to be able to explain if asked "why isn't the #1 global
track in this chart?"

### KPI 2: choosing a scatter plot over a grouped bar chart
PROJECT_PLAN.md's original spec suggested a grouped bar for this KPI (global rank bar
next to country rank bar, per track). Built that version first, but reconsidered after
direct feedback during the build ("again a bar chart?") — and on reflection, a scatter
plot is actually the more correct visualization here, not just a different one: this
KPI compares two PAIRED numbers (global rank, country rank) for the same entity, which
is the textbook use case for a scatter plot (X = one value, Y = the other, each point's
position directly shows the relationship) rather than two bars that have to be visually
compared side by side. Final version: X-axis = Global Rank, Y-axis = Country Rank, one
point per track/country pair. Reading the chart: every point sits well below the
imaginary diagonal (where global rank = country rank), since the underlying query
already selected for the biggest such gaps — that visual gap IS the story.

### KPI 2: a color-coding tradeoff — when a "cleaner" fix is the wrong fix
With 10 distinct points needing 10 distinct colors, Metabase's default palette ran out
and started repeating (3 colliding pairs, e.g. two different tracks both rendered blue).
First fix attempted: switch the series breakout from per-track to per-COUNTRY — since
the 10 points only span 4 countries, this technically eliminated the collision entirely
(4 colors needed, palette easily covers that). But it made the chart **worse**: KPI 2's
whole point is specific surprising TRACKS (Malcolm Todd, Sabrina Carpenter, etc.), and
coloring by country shifted the visual story toward country clustering instead, while
also removing per-track identification from the legend — a real loss on a static
presentation slide where hovering for a tooltip isn't possible. Reverted, and instead
manually reassigned colors on just the 3 colliding pairs via Metabase's color picker
(the palette had ~16 usable colors across a light/dark row, more than enough for 10 —
the problem was never a true shortage, just an automatic assignment that didn't check
for duplicates). **Lesson, good for a presentation soundbite:** the technically simpler
fix (fewer colors needed) wasn't the right fix, because it solved the rendering problem
while breaking the chart's actual communication goal — worth always asking "does this
fix solve the technical bug, or does it also still tell the story I need it to tell?"

### Why KPI 2 ended up as a Metabase SQL question, not a dbt model
Back in Phase 5, we deliberately deferred deciding whether "global vs country" needed
its own dbt model or could be a direct query, until we actually knew the shape Metabase
needed (see "Why a single fact table grain works for most KPIs" above). Now resolved:
it's a Metabase-only native SQL question, not a dbt model. Reasoning: this comparison is
purely a presentation-layer concern (how do we SHOW the data) rather than a reusable
transformation other parts of the project depend on — nothing else needs "global rank
vs country rank" as an intermediate table, so promoting it into dbt would have added a
model with exactly one consumer. Good general rule worth stating in interviews: build a
dbt model when multiple things need the same transformed data; write it directly in the
BI tool when only one chart needs that exact shape.

### Assembling the dashboard: one tab, and a chart-type swap driven by real data
Combined all 5 saved questions into a single Metabase dashboard, one tab (not multiple)
— with only 5 charts, one scrollable page is easier to present from than clicking
between tabs, and there isn't enough distinct content yet to justify splitting. Laid out
as a 2-column grid for 4 of the charts, with KPI 3 (genre breakdown, 24+ genre
categories) widened to the full dashboard width — it needed more horizontal room than
half-width gave it.

While assembling, found that 3 charts were displaying raw Postgres join-path strings as
their axis titles (e.g. "Dim Date - Date Key → Snapshot Date" instead of just "Snapshot
Date") — these default to the literal joined-column path unless you override them, easy
to miss when building one question at a time but obvious once everything sits together
on one dashboard. Fixed via each question's Axes tab settings.

KPI 1 also needed a genuine chart-type change at this stage, not just a label fix: its
X-axis labels ("Artist — Track", e.g. "Olivia Rodrigo — drop dead") were long enough
that even enlarging the card still left them cramped and rotated. Switched from a
vertical Bar chart to a **Row chart** (horizontal bars) — track names now read as normal
left-aligned text instead of needing rotation, and bars extend rightward by playcount.
**Presentation line:** this isn't just a workaround — horizontal row/leaderboard charts
are the standard pattern for "Top 10" style rankings in real music-industry dashboards
(Spotify, Billboard), so the long labels actually pointed toward the more idiomatic
chart type for this specific KPI, not just a fix for a cosmetic problem.

---

## Hurdles encountered and how we solved them

### Hurdle: connecting local git to GitHub
When the GitHub repo was created via the UI, it auto-generated a README. When we tried
to push our local files, git rejected it because the two histories had never been
connected. Fix: `git pull origin main --allow-unrelated-histories` to merge the two
histories first, then push.

### Hurdle: vim opened during git merge
During the merge, git opened vim to ask for a merge commit message. As a beginner this
was unexpected. Fix: type `:wq` to save and exit vim.

### Hurdle: country chart ranks were 0-based
The `geo.getTopTracks` endpoint returns ranks starting at 0 (0, 1, 2...) instead of 1.
The global chart ranks start at 1. Fix: add +1 to every country rank so all charts use
the same 1-based system.

### Hurdle: genre tags were junk for some tracks
Some tracks had no real genre tags — only usernames and personal labels like
`['julia mofada', 'brighterdayinc', 'isa-song']`. Fix: KNOWN_GENRES allowlist.
Also found that `rnb` and `r&b` are both used as tags — added both to the list.
Also added sub-genres like `pop rock`, `indie pop`, `synthpop` to reduce unknowns.

### Hurdle: dbt tests caught a real duplicate-surrogate-key bug once more days accumulated
This is a good story for the presentation — it's a real example of tests catching a real bug,
not a contrived demo. While connecting Metabase, noticed Postgres was stuck at 2026-06-17 even
though the cloud pipeline had clean data in S3 through 6-20 (a 3-day gap from a silently-failing
local cron job — see the cron hurdle below). After backfilling those 3 days and rerunning
`dbt run`, 11 of 24 tests suddenly failed: 1 duplicate `artist_key`, 10 duplicate `track_key`.
With only 3 days of data these had never shown up — they needed enough days for the same
artist/track to appear with slightly different metadata on different snapshots.

Investigated both failures by querying the actual duplicate rows directly (not guessing):
- **dim_artist:** Justin Bieber — same name, same MusicBrainz ID, but the `artist_origin_country`/
  `artist_type`/`artist_gender`/`artist_begin_year` columns were fully populated on 5 of 6 days and
  completely blank on 2026-06-19 only. This points to a transient MusicBrainz API failure (timeout
  or rate-limit) during that single day's Glue enrichment run — not a missing artist, just one bad
  lookup that fell back to the "not found" empty result.
- **dim_track:** 10 tracks (mostly Olivia Rodrigo's catalog) got a *different* `track_mbid` from
  Last.fm on different days for the exact same track name + artist (e.g. "begged" had mbid
  `977a73bd...` on one day and `17a144ec...` on another). This means Last.fm's mbid linking for a
  track isn't fully stable across API requests — a genuine, interesting real-world data-quality
  finding, not a bug in our code.

**Root cause in our own SQL, not the source data:** `dim_artist.sql` and `dim_track.sql` both used
`SELECT DISTINCT` across *all* columns (identity columns + metadata columns together). Our
surrogate key (`artist_key` / `track_key`) is deliberately computed from only the *identity*
columns (name + mbid, or name + artist) — so whenever a metadata column differed between two
days for the same identity, `SELECT DISTINCT` produced two separate rows that both hashed to the
identical key. That's precisely the edge case we'd worried about and built the `unique` test for
back when we first designed `dim_artist` — it just took more days of real data to actually trigger it.

**The fix:** changed both models from `SELECT DISTINCT` to `GROUP BY` the identity columns, with
`MAX()` applied to every metadata column. Two things `MAX()` buys for free: (1) `GROUP BY`
guarantees exactly one row per surrogate key — duplicates become structurally impossible; (2)
`MAX()` ignores `NULL`s, so it automatically "self-heals" gaps — Justin Bieber's blank 6-19 row
gets silently replaced by the real `CA / Person / Male / 1994` values pulled from any of the other
5 good days. Reran `dbt test`: 24/24 passing again, with the underlying data quietly fixed.
**Presentation line:** "Our dbt tests aren't just boilerplate — they caught a real data
inconsistency caused by a flaky third-party API call, and the fix was a one-line aggregation
change that also self-heals future gaps of the same kind."

### Hurdle: local cron job for the S3 -> Postgres loader silently wasn't firing
Root-caused via two live, controlled tests rather than guessing: scheduled one test cron job
writing to a file in the home directory, and a second writing to a file inside the Desktop-based
project folder. **Both succeeded** — which ruled out the "macOS Full Disk Access" theory we'd
suspected back in an earlier session (Desktop/Documents/Downloads are TCC-protected on macOS, and
we'd assumed that was blocking cron). With that ruled out, the most likely explanation is the
one we'd already half-suspected: the Mac is asleep at 10:15am most mornings, and cron does not
wake a sleeping machine — a skipped run leaves absolutely no trace (no log line, no error, nothing).
**Decision:** don't fight macOS power-management settings for a local-only convenience script —
not worth the effort/risk this close to the deadline. The cloud pipeline's SNS email notification
already confirms every day when fresh data is sitting in S3, so a missed local sync is easy to
spot and fix with a quick manual backfill, which is itself now a single command (see below).

### Hurdle: country charts missing playcount
The `geo.getTopTracks` endpoint doesn't always return `playcount`. Our code crashed
with `KeyError: 'playcount'`. Fix: use `.get("playcount", None)` instead of
`track["playcount"]` — returns None gracefully if the field is missing.

---

## Data quality checks (built into the pipeline)

Run automatically every time `pipeline.py` runs:
- **No duplicate rows** — same track + chart + date should never appear twice
- **50 rows per chart** — catches silent API failures
- **No null track_name or artist_name** — core identity fields
- **Ranks 1–50** — validates both global (derived) and country (fetched) ranks
- **Unknown genre count** — informational; 119/300 is expected and acceptable (see genre limitation note above)

---

## Session log (newest first)

### Session 13 — 2026-06-22 (Phase 7 complete: KPI 5 finished, KPI 2 built — all 5 KPIs done)
Mac was asleep again at the 10:15am cron time (3rd day in a row — the accepted fallback
pattern from Session 11 continues to hold up fine). Ran `./run_daily_pipeline.sh 2026-06-22`
manually, 24/24 tests passed, now 8 days of data.
- Finished KPI 5: switched to bar chart, X=track_artist, Y=rank_change, color breakout by
  the `direction` column, enabled "show values on data points" so each bar displays its
  exact +/- number directly. Saved as "KPI 5 - Biggest Movers (Climbers & Fallers, Global)".
- Built KPI 2 (global vs country) entirely from scratch — see the three new design-decision
  entries above ("KPI 2: a self-join...", "KPI 2: choosing a scatter plot...", "KPI 2: a
  color-coding tradeoff...") for the full story. Short version: first self-join in the
  project; deliberately sorted for the biggest global/country rank mismatches instead of
  the obvious sort order, which surfaced a genuinely good story (regional hits like
  Malcolm Todd); switched from grouped bar to scatter plot as a better-fit chart type;
  worked through a real color-collision tradeoff (technically-simpler fix vs. the fix that
  actually preserved the chart's story) and landed on manually fixing 3 color pairs.
  Saved as "KPI 2 - Global vs Country (Biggest Regional Hits)".
- **All 5 KPIs are now built and saved as individual Metabase questions.** This closes out
  the chart-building part of Phase 7.
- Assembled all 5 into one Metabase dashboard (single tab, ordered KPI 1 -> 4 -> 5 -> 2 -> 3,
  KPI 3 widened to full width) — see "Assembling the dashboard" design decision above for
  the full story, including fixing 3 charts' raw join-path axis labels and switching KPI 1
  from a vertical bar to a row chart to fix long, cramped track/artist labels.
- **Phase 7 is now fully complete** — all 5 KPIs built, polished, and assembled into one
  dashboard. Per the settled build order, Phase 6 (GitHub Actions) is next, then Phase 8
  (docs/demo). Possible future polish if time allows: a second dashboard tab for more
  creative/exploratory views — not committed to, just an idea raised in conversation.

### Session 11 — 2026-06-20 (Phase 7 started: Metabase + a real data-integrity bug)
Installed Docker, ran Metabase as a container (port 3000, persistent volume `metabase-data` so
dashboard work survives restarts), connected it to local Postgres via `host.docker.internal`
(containers can't reach the host machine through `localhost`) — confirmed all 9 Postgres tables
visible in Metabase's data browser.
- Before building any KPIs, found and fixed a real 3-day data gap and a real duplicate-surrogate-
  key bug — see "Hurdle: dbt tests caught a real duplicate-surrogate-key bug" and "Hurdle: local
  cron job ... silently wasn't firing" above for the full story and root-cause investigation.
  Short version: backfilled 6-18/6-19/6-20 from S3, which surfaced 11 dbt test failures once 6
  days of real data existed; fixed dim_artist.sql and dim_track.sql (SELECT DISTINCT -> GROUP BY
  + MAX()); 24/24 tests passing again, with the fix also self-healing the underlying gap.
- Built run_daily_pipeline.sh (see "Why chain dbt into the daily load" above) so dbt tests run
  automatically every time data is loaded, whether via cron or manual backfill, going forward.
- Next: build the first Metabase questions — KPI #1 (top tracks now), #3 (genre breakdown by
  country), #4 (trend over time), #5 (biggest movers) — all answerable directly off
  fact_chart_entry / fact_chart_entry_trends. KPI #2 (global vs country) still deferred until we
  know the exact shape needed.

### Session 10 — 2026-06-18 (conceptual: dbt explained, KPI feasibility, project depth strategy)
No code changes besides docs. A learning-focused session to cement understanding before
moving into Metabase.
- Walked through dbt vs. Postgres conceptually (kitchen analogy: Postgres is the kitchen
  where food/data actually lives; dbt is the recipe book + sous-chef that tells the
  kitchen what to cook and in what order, then steps aside). See "Why use dbt at all"
  design decision above for the full answer.
- Toured the lineage graph live via `dbt docs serve` — confirmed visually that
  raw_chart_entries -> stg_chart_entries -> 5 dims + fact_chart_entry -> fact_chart_entry_trends
  matches the intended design.
- Added a cross-reference note to docs/PROJECT_PLAN.md so it doesn't contradict
  CLAUDE.md's settled build order (Metabase before GitHub Actions despite the phase
  numbers running 6-then-7) — both docs now agree on what's actually next.
- Pre-checked KPI feasibility against existing tables before starting Metabase — see
  "Why a single fact table grain works for most KPIs" above. Result: only 1 of 5 KPIs
  needs new modeling work (a self-join for "global vs country"), deferred until Phase 7.
- Addressed a project-depth/complexity worry: recommended finishing the 3 remaining
  basics (Metabase, GitHub Actions, Phase 8 docs) before revisiting the Terraform/
  Snowflake stretch goals, consistent with the already-settled July 1 checkpoint.
  Reframed that real depth already exists independent of infra tooling: a genuine star
  schema with deterministic surrogate keys, multi-source enrichment (Last.fm +
  MusicBrainz), window functions, and 24 passing dbt tests. Pace estimate: ~4 more
  sessions to finish the basics (2 for Metabase, 1 for GitHub Actions, 1 for Phase 8),
  comfortably inside the July 1 checkpoint and the July 10 presentation date.

### Session 9 — 2026-06-18 (Phase 5: window functions)
Closed out Phase 5 by adding rank_change.
- Built fact_chart_entry_trends.sql — see "rank_change: LAG() window function, sign
  convention" design decision above for the full mechanics.
- 900 rows, 10/10 new tests passing (24/24 total project-wide). Spot-checked the top
  movers directly in psql to confirm correctness against real data (one track moved
  from rank 42 to rank 26 — correctly showed rank_change = +16).
- This closes Phase 5 entirely (all checklist items done). Next: Phase 7 — Metabase.

### Session 8 — 2026-06-17 (Phase 5: star schema)
Built the full star schema in dbt.
- Design discussion before any code: fact grain = one row per track, per chart, per day
  (matches the existing 300 rows/day). 5 dimensions: dim_artist, dim_track, dim_genre,
  dim_country, dim_date. Talked through WHY split fact/dimension at all — avoids
  repeating descriptive text (artist profile, genre, etc.) on every fact row; dimension
  tables let you fix data in one place and keep storage lean.
- Surrogate keys: decided to generate our own via md5() hash of natural keys, rather than
  trusting source IDs (artist_mbid/track_mbid) directly. Reasons: source MBIDs are
  sometimes missing (~3% of artists), some dimensions have no source ID at all
  (dim_country, dim_genre, dim_date), and a single consistent method is simpler to
  explain and maintain than mixing approaches per dimension.
- Why md5() instead of ROW_NUMBER()/sequential IDs: md5 is deterministic — the same
  artist always hashes to the same key, every dbt run. Sequential IDs could shift
  between reruns depending on row order, silently breaking every fact-to-dimension join.
- Built dim_genre (27 rows), dim_country (6 rows), dim_date (3 rows, with year/month/day/
  day_of_week derived columns), dim_artist (75 rows), dim_track (141 rows).
- fact_chart_entry: recomputes the same md5() hash inline per dimension (no actual SQL
  JOIN needed, since the hash is deterministic) — 900 rows = 3 snapshots x 300 rows,
  confirming the transformation didn't lose or duplicate any rows.
- Tests: unique + not_null on dim_artist.artist_key and dim_track.track_key (catches
  the edge case where the same artist/track could get inconsistent metadata across
  rows — would show up as a duplicate key, caught by the unique test). not_null +
  relationships tests on every foreign key in fact_chart_entry (verifies every fact
  row successfully matches a real dimension row). 14/14 tests passing.
- Visualized with dbt docs generate + serve — lineage graph confirms
  raw_chart_entries -> stg_chart_entries -> 5 dims + fact_chart_entry.
- dbt-core version note: `pip install dbt-postgres` initially pulled in dbt-core
  2.0.0-alpha.1 as a dependency (unstable). Force-installed dbt-core==1.8.8 to match
  dbt-postgres==1.8.2 — both stable, compatible versions.

### Session 7 — 2026-06-17 (cron cleanup)
Verified the cloud pipeline's second daily run, then cleaned up local automation.
- 8:00am EventBridge-triggered run succeeded; clean file landed in S3 as expected.
- The 8:15am local cron job (S3 → Postgres loader) silently failed to fire — no log
  entry at all. Likely cause: Mac asleep, or Full Disk Access grant not yet fully
  effective. Manually ran load_to_postgres.py and confirmed it works (300 rows loaded
  for 2026-06-17) — the script itself is fine, only the cron trigger is unreliable.
- Moved the local loader cron job to 10:15am, giving the cloud pipeline a wider buffer.
- Removed the old 10:00am `run_pipeline.sh` cron job. That job was the pre-cloud full
  local pipeline (fetch from Last.fm/MusicBrainz directly). It became redundant once
  Glue took over fetch+enrich in Phase 3, and was silently duplicating API calls every
  morning — harmless only because of the duplicate-date guard in load_to_postgres.py.
  Lesson: when a manual/local process gets replaced by automation, remove it — don't
  leave it running "just in case," it wastes API quota and can mask real failures.
- Current state: ONE local cron job (10:15am S3 loader). The 8am cloud run is the
  source of truth; the local job's only purpose is bridging cloud S3 to local Postgres.

### Session 6 — 2026-06-16 (Phase 4)
Full cloud orchestration and notification layer.
- Step Functions state machine (music-charts-pipeline): chains Glue Job #1 → Job #2.
  Each job has a Retry block (2 retries, 30s interval, 2x backoff) and a Catch that routes
  to NotifyFailure if all retries are exhausted.
- NotifySuccess / NotifyFailure states call Lambda at the end of every run.
- Lambda function (music-charts-notify): publishes to SNS with a subject line showing
  SUCCESS or FAILED. SNS delivers to email (orontavor@gmail.com). Confirmed working —
  received success email after test execution.
- EventBridge schedule (music-charts-daily): fires daily at 08:00 Berlin time (UTC+2).
  Triggers the Step Functions state machine. Schedule type: Standard (not Express) because
  we need .sync Glue integration which Express doesn't support.
- Local loader updated: load_from_s3() pulls today's clean S3 file into Postgres.
  Duplicate guard preserved — safe to run multiple times.
- Cron job at 8:15am runs load_to_postgres.py — 15 min after cloud pipeline starts,
  enough buffer for both Glue jobs to finish (~3 min total).
- IAM note for interviews: two IAM users — oront (console/UI work) and terra_proj
  (programmatic/CLI). Lambda needed SNS publish permission added to its execution role.
- Terminal Full Disk Access granted on Mac so cron jobs actually fire.

### Session 5 — 2026-06-15 (Phase 3)
Moving the pipeline to AWS Glue.
- Set up billing alerts: zero-spend budget (already active) + $20 monthly budget with
  alerts at 85% ($17) and 100% ($20) + forecast alert. AWS budget cap is firm at $20.
- IAM hurdle: terra_proj user needed AWSGlueConsoleFullAccess + iam:PassRole permission.
  Also: Glue service role must be named AWSGlueServiceRole-* for PassRole to work via
  AWSGlueConsoleFullAccess — naming convention matters, not obvious to beginners.
- Decision: create Glue jobs via UI (avoids PassRole CLI friction), verify via CLI.
- Glue role created: AWSGlueServiceRole-music-charts (S3FullAccess + AWSGlueServiceRole).
- Job #1 (music-charts-fetch): Python Shell, 1/16 DPU, 30min timeout.
  Fetches Last.fm global + 5 country charts → saves raw/YYYY-MM-DD/charts_raw.csv to S3.
  Ran successfully in ~20 seconds. Verified raw file in S3 (54KB).
- Job split rationale: Job #1 = raw fetch only. Job #2 = enrichment only.
  If Job #2 fails, raw data is safe in S3 and Job #2 can be rerun without hitting Last.fm again.
- Job #2 (music-charts-enrich): reads raw S3 file, adds genre (Last.fm tags) +
  artist metadata (MusicBrainz), runs quality checks, saves clean/YYYY-MM-DD/charts_clean.csv.
- Key technical difference from local pipeline: no local filesystem in Glue.
  Use io.StringIO() buffer + s3_client.put_object() to write to S3.
  Use s3_client.get_object() + io.BytesIO() to read from S3.

### Session 4 — 2026-06-15
Completed Phase 2b and set up daily automation.
- Built src/musicbrainz.py: second data source client. Respects 1.1s rate limit.
  Retries with exponential backoff. _empty_result() fallback for missing MBIDs.
- Added artist_mbid column to both fetch_global() and fetch_country() in pipeline.py.
- New enrich_with_artist_metadata() function: deduplicates by artist_mbid first,
  looks up each unique artist once, maps results back onto all 300 rows.
- 4 new columns in output: artist_origin_country, artist_type, artist_gender, artist_begin_year.
- Coverage: 291/300 rows have artist_origin_country. Top origins: US(27), GB(12), JP(8), KR(7).
- Genre unknown rate settled at 119/300 after expanding KNOWN_GENRES list.
  Investigated root cause: 80% of unknowns have ZERO tags on Last.fm — not a fixable problem.
  Documented as a known limitation of crowd-sourced tagging for non-Western markets.
- Hurdle: wrong hardcoded MBID in test returned wrong artist silently — no error from
  MusicBrainz. Lesson: always use MBIDs from Last.fm directly, never guess them.
- load_to_postgres.py rewritten to APPEND (not replace) with a duplicate guard:
  checks if snapshot_date already exists before loading — safe to run pipeline twice.
- First daily snapshot loaded: 2026-06-15, 300 rows in raw_chart_entries table.
- Daily automation: cron job at 10:00am via run_pipeline.sh. Mac desktop notification
  on success and failure. Output logged to pipeline.log (git-ignored).
- AWS budget cap set: $20 max for entire project. Billing alerts to be set at $10
  (warning) and $20 (stop) as FIRST step of Phase 3.

### Session 3 — 2026-06-12
Building Phase 2b: MusicBrainz enrichment.
- Decision to build Phase 2b was data-driven, not assumed. Before writing any code we
  ran two pre-flight checks:
  1. Artist MBID coverage from Last.fm: 97% of 300 rows had a non-empty artist MBID
     (80 out of 85 unique artists). Only 5 artists missing — those default to None.
  2. MusicBrainz field coverage for a sample of 15 artists: country=100%, type=100%,
     begin_year=100%, gender=73% (missing only for bands/groups — correct, not a bug).
- Join key: artist MBID (from Last.fm) → MusicBrainz artist record.
  Clean join — no fuzzy matching needed. "Not found" defaults to None gracefully.
- New KPI unlocked: "country of origin vs country of consumption" — which countries
  PRODUCE charting artists vs which IMPORT them? E.g. does Japan's chart favor
  local artists? Are Korean artists (BTS etc.) disproportionately popular outside Korea?
- Architecture: adding src/musicbrainz.py (second data source client) + artist_mbid
  column to pipeline.py rows + enrich_with_artist_metadata() function.

### Session 2 — 2026-06-11
Built Phase 2: the full pipeline.
- Created src/lastfm.py: API client with retries, exponential backoff, rate-limit pause,
  and three endpoint functions (global chart, country chart, track tags + genre picking).
- Created pipeline.py: fetches global + 5 countries, enriches with genre, quality checks,
  saves charts_clean.csv (300 rows).
- Encountered and fixed: 0-based country ranks, missing playcount field, junk genre tags.
- Key decision: KNOWN_GENRES allowlist for genre, "unknown" as intentional fallback.
- Added WHY comments to both files — explains non-obvious decisions for interviews.
- Created this file (docs/PRESENTATION_NOTES.md) as a running presentation reference.
- dbt tests plan confirmed: built-in tests only (not_null, unique, accepted_values,
  relationships) — no custom tests unless ahead of schedule.
- Daily automation: cron job runs run_pipeline.sh at 10:00am every day. On success/failure
  a Mac desktop notification fires. Output logged to pipeline.log. This is temporary —
  Phase 3-4 (AWS Glue + Step Functions) replaces it with cloud automation and SNS alerts.

### Session 1 — 2026-06-10
Built Phase 0 (setup) and Phase 1 (thin slice).
- Created GitHub repo, connected local folder via git init + remote add + push.
- Set up Python venv, installed requests/pandas/boto3/python-dotenv/psycopg2/sqlalchemy.
- Created AWS S3 bucket: music-charts-pipeline-orontavor.
- Got Last.fm API key, stored in .env (git-ignored).
- Created Postgres database music_charts (user: orontavor, port: 5432).
- fetch_global.py: first working API call, saved to CSV.
- load_to_postgres.py: loaded CSV into Postgres, confirmed rows visible in pgAdmin.
- Proved the full local path: API → CSV → Postgres.
