# CLAUDE.md — Project Briefing

This file orients you (Claude Code) at the start of every session. Read it first, then read docs/PROJECT_PLAN.md for full detail.

## STANDING INSTRUCTIONS (do these automatically, every session)

1. At the START of a session: read the "Progress log" section below and tell me where we left off and what the next step is.
2. As we COMPLETE things: keep the Progress log accurate (mark items done, move the [~] in-progress marker, add a short "Session notes" line).
3. Near the END of a session, or whenever I say I'm stopping: remind me, and update the Progress log yourself before we finish — don't wait for me to remember.
4. After finishing a meaningful piece, suggest a git commit with a clear message. These keep the project's memory in the files, so we never lose our place if the chat history resets.
5. At the END of every session: update docs/PRESENTATION_NOTES.md with any new decisions made, hurdles encountered, and what was built. This is the user's presentation reference document.

## What this project is

A data-engineering capstone: an automated pipeline that fetches live music chart data from the Last.fm API — the GLOBAL chart PLUS the top chart for 5 countries (United States, United Kingdom, Germany, Brazil, Japan) — enriches it with genre (Last.fm tags) and artist metadata (MusicBrainz: origin country, type, gender, formation year), stores it in AWS S3, loads it into a LOCAL Postgres warehouse, models it as a STAR SCHEMA with dbt, and shows trend KPIs in a Metabase dashboard. It runs daily and builds up a time series so we can see what's rising, falling, and trending — globally and per country.

The geo/country layer is CORE (not optional): it adds real ingestion volume (loop over 5 countries), a star-schema modeling exercise (fact + track/artist/genre/ country/date dimensions), and a genuine cross-chart join. This is a data-engineering project, so that pipeline substance is the point — not BI polish.

The full plan (business context, data source, schema, KPIs, phases, tools) is in: docs/PROJECT_PLAN.md Always consult it before building. It is the source of truth.

Note: the data fields in the plan have been verified against the live Last.fm API. The plan marks each column as FETCHED (returned by the API) or DERIVED (we compute it). Key things to remember:

- The GLOBAL chart (chart.getTopTracks) does NOT return a rank number -> derive it from list order.
- The COUNTRY charts (geo.getTopTracks) DO return a rank attribute -> rank is fetched there.
- geo.getTopTracks takes country = an ISO country NAME (e.g. "united states", "germany").
- geo track-level mbid is OFTEN EMPTY -> joins to the global chart fall back to name matching.
- geo is "most popular LAST WEEK"; global is "now" -> slightly different time windows (documented).
- geo returns no "listeners" field (global does) -> listeners is null for country rows.
- "genre" comes from crowd "tags" (top tag, needs cleaning), not a genre field.
- The 5 countries: United States, United Kingdom, Germany, Brazil, Japan.

## Tech stack

- Python + pandas (fetching + cleaning)
- AWS S3 (cloud storage), AWS Glue (runs our code in cloud), AWS Step Functions (orchestration), AWS Lambda + SNS (notifications)
- PostgreSQL (LOCAL) as the warehouse — NOT Snowflake. Reason: Snowflake's free trial is only 30 days, which doesn't fit a 4-week project. Postgres is free forever and already installed locally (pgAdmin). We KEEP all the AWS pieces so the cloud-ingestion skills are still demonstrated.
- dbt (dbt-postgres adapter) — SQL transformations, runs against local Postgres
- GitHub Actions (CI/CD — auto-runs dbt tests)
- Metabase (dashboard, runs locally via Docker, connects to Postgres)
- Git/GitHub (version control)

IMPORTANT loader detail: AWS can't reach the local Postgres, so a small local Python script pulls the clean file down from S3 and writes it into Postgres (pandas read from S3 -> to_sql into Postgres). This replaces Snowflake's "external stage" step.

## Build strategy — IMPORTANT

Build LOCAL-FIRST, then lift to the cloud.

1. Get the whole pipeline working on my laptop first (Python -> file -> local Postgres -> dbt -> Metabase). S3 comes in when we move to Glue.
2. ONLY THEN move the Python into AWS Glue + Step Functions as an upgrade layer. Reason: I always want a working version. If the cloud pieces fight me near a deadline, the local version is still a complete, submittable project.

## About me (the developer) — please respect this

- I am a rookie / beginner with most of this stack. Go step by step.
- I want to LEARN, not just receive finished code. A goal of this project is to be able to explain the code in job interviews.
- So: build in SMALL steps. After writing something, briefly explain what it does and why. Don't autopilot through many steps at once.
- Check in with me before big moves (installing things, creating many files, anything that costs money on AWS).
- Prefer the simplest thing that works. Avoid cleverness I won't understand.
- If I seem confused, slow down and explain in plain words.

## Money / safety notes

- **AWS budget cap: $20 for the entire project.** Set a billing alert in AWS BEFORE starting Phase 3 — alert at $10 (warning) and $20 (hard stop). Do this as the FIRST step of Phase 3, before creating any Glue jobs.
- Realistic AWS cost breakdown: S3 ~$0, Glue ~$8-15 total (at minimum 2 DPUs, ~$0.20-0.30/run), Step Functions ~$0, Lambda/SNS ~$0.
- Glue risks: default DPU is 10 (not 2) — always set to 2 explicitly. Always set a job timeout to prevent runaway billing if the API hangs.
- NO secrets (API keys, passwords) in code or git. Use a .env file (git-ignored) or environment variables. Remind me if I'm about to commit a secret.

## Progress log — UPDATE THIS EVERY SESSION

This is the project's memory. At the START of each session, read this to see where we left off. At the END of each session, update it (mark items DONE, note what's IN PROGRESS and what's NEXT). This way any fresh Claude Code session can pick up exactly where we stopped, even if the chat history is gone.

Status key: [ ] todo · [~] in progress · [x] done

### Build order plan (SETTLED 2026-06-18)

Presentation date: July 10, 2026. Goal: fully working + polished by end of first week
of July, leaving ~1 week for rehearsal/polish before the 10th.

Priority order for remaining work:
1. [x] dbt window functions (rank_change, biggest movers) — unblocks dashboard KPIs — DONE 2026-06-18
2. [x] Phase 7 — Metabase dashboard (core deliverable, explicitly promised in project description) —
   DONE 2026-06-22. All 5 KPIs built and assembled into one dashboard.
3. Phase 6 — GitHub Actions (dbt tests on push)
4. Phase 8 — docs, architecture diagram, demo script

**Terraform (IaC) is a STRETCH goal, not in the original 8 phases.** Added only to close
a gap vs. a classmate's project (they used Terraform + Airflow; we used manual AWS console
setup + dbt CLI). Plan: use `terraform import` to bring already-existing AWS resources
(S3, Glue x2, IAM roles, Step Functions, EventBridge schedule, Lambda, SNS) under Terraform
management WITHOUT recreating them — zero risk to the working pipeline.
TRIGGER: only attempt this if steps 1-4 above are done before ~July 1. If not done by then,
skip it entirely and spend the remaining time on rehearsal/polish instead.
>>> When steps 1-4 are complete, proactively remind the user it's time to consider Terraform. <<<

### Phase 0 — Setup

- [x] Create GitHub repo + README skeleton
- [x] Python virtual environment + requirements.txt
- [x] Confirm local Postgres works (pgAdmin) — db: music_charts, user: orontavor, port: 5432
- [x] Create AWS account + an S3 bucket — bucket: music-charts-pipeline-orontavor
- [x] Get Last.fm API key (store in .env, NOT in code)
- [x] Install Docker (for Metabase later — can wait)

### Phase 1 — Thin slice (local)

- [x] Python: fetch GLOBAL chart once, save to a file
- [x] Load that file into Postgres by hand
- [x] See the rows in Postgres (pgAdmin) — proves the path end to end

### Phase 2 — Python fetch + clean (local)

- [x] API client (requests wrapper, timeout, retries, rate-limit pause)
- [x] Derive global rank from list order
- [x] Loop over the 5 countries (geo.getTopTracks)
- [x] Enrichment loop: genre per track (track.getTopTags), clean tags
- [x] pandas: combine global + 5 countries into the tidy table
- [x] Quality checks (no nulls/dupes; count matched rows after joins)

### Phase 2b — MusicBrainz enrichment (DONE)
> Pre-assessed on 2026-06-12: 97% of rows have artist MBID; 100% country/type/begin_year
> coverage in MusicBrainz sample of 15 artists; 73% gender (missing only for bands — expected).
- [x] MusicBrainz lookup by artist MBID -> origin country, begin year, type, gender
- [x] respect 1.1s rate limit; handle "no MBID/not found" with _empty_result()
- [x] pipeline output extended with 4 new columns; load_to_postgres.py appends daily

### Phase 3 — Move code into AWS Glue

- [x] Glue Job #1 "Fetch" (global + 5 countries) -> S3 raw/
- [x] Glue Job #2 "Enrich/flatten" -> S3 clean/
- [x] IAM permissions (go slow, test one piece at a time)

### Phase 4 — Orchestrate (Step Functions + Lambda/SNS)

- [x] Step Functions: run Job #1 then #2 with retries
- [x] Lambda + SNS success/failure notification
- [x] Schedule daily
- [x] Local loader: pull clean file from S3 -> write into Postgres

### Phase 5 — dbt star schema (Postgres)

- [x] dbt-postgres set up + connected
- [x] sources -> staging -> marts (fact_chart_entry + 5 dims)
      staging: sources.yml + stg_chart_entries.sql
      dims: dim_artist (75 rows), dim_country (6), dim_date (3), dim_genre (27), dim_track (141)
      fact_chart_entry: 900 rows (3 days x 300 rows) — surrogate keys via md5() hash
- [x] window functions (rank_change, biggest movers)
      fact_chart_entry_trends: LAG(rank) over (partition by track_key, country_key order by snapshot_date)
      rank_change = previous_rank - rank (positive = climbed, negative = fell); 900 rows, 10/10 tests passing
- [x] dbt tests + docs/lineage
      24 tests passing (unique/not_null on dim keys, not_null + relationships on all fact + fact_trends FKs)
      lineage graph verified via dbt docs generate + serve
- [ ] (stretch, optional) incremental models / rolling averages / SCD / custom tests
      — see "Phase 5 depth options" in PROJECT_PLAN.md; only if ahead of schedule

### Phase 6 — GitHub Actions

- [ ] Workflow that runs dbt tests on push

### Phase 7 — Dashboard (Metabase)

- [x] Metabase via Docker, connected to Postgres
      Container `metabase` running via docker run, persistent volume `metabase-data` so dashboards
      survive restarts. Connected to local Postgres using host.docker.internal:5432/music_charts
      (containers can't reach the host via localhost). All 9 tables visible in Metabase's data browser.
- [x] Build the 5 KPIs
      KPI 1 (Top Tracks Now - Global) DONE: bar chart, joins fact_chart_entry -> dim_track/dim_artist/
      dim_country/dim_date, filtered to chart_scope=global + snapshot_date=today, sorted by rank asc,
      limit 10. Custom column concat(Artist Name, " — ", Track Name) used as X-axis label since neither
      raw column alone shows both. Y-axis = Playcount (chose this over Rank since rank is an ordering,
      not a magnitude — using it as bar height would visually invert "better"). Saved as
      "KPI 1 - Top Tracks Now (Global)".
      KPI 3 (Genre breakdown by country) DONE: stacked bar, joins fact_chart_entry -> dim_country +
      dim_genre, filtered to chart_scope != global + snapshot_date=today, Summarize (Count, group by
      Chart Scope + Genre). Metabase auto-chose genre on X-axis with country stacked inside each bar
      (kept this orientation — equally valid, arguably more readable than country-on-X). "unknown"
      genre dominates the chart (~90 entries) — kept deliberately rather than filtered out, ties to the
      documented genre-coverage limitation (~42% unknown), decided to use as a presentation talking
      point rather than hide it. Saved as "KPI 3 - Genre Breakdown by Country".
      KPI 4 (Trend over time) DONE: line chart, same 4 joins as KPI 1, filtered to chart_scope=global +
      rank<=5 (capped at 5 lines after rank<=10 caused color collisions with 12 lines), X-axis=Snapshot
      Date, Y-axis=Rank, series=Track (Artist) custom column. Tried flipping the Y-axis intuition with a
      "51 - Rank" custom column (so climbing the chart visually goes up) — this BACKFIRED: with only
      ranks 1-5 in view, the transform compresses everything into a tiny 4-point band near the top of an
      implied 0-50 scale, hiding the line crossings. Reverted to raw Rank (auto-scales to the small 1-5
      range, crossings clearly visible) and deleted the unused custom column. Lesson: an axis "fix" that
      solves a problem in the abstract can hurt readability once the data range is already narrow — kept
      raw Rank, added a verbal caveat instead ("lower = better") rather than transforming the data.
      Saved as "KPI 4 - Trend Over Time (Global Top 5)".
      KPI 5 (Biggest movers) DONE: native SQL query (not the GUI notebook builder), since Metabase's
      visual builder can only sort+limit in one direction per question, and this KPI needs BOTH ends at
      once (top 5 climbers + top 5 fallers) for a diverging bar chart. Query is a UNION ALL of two
      near-identical SELECTs (one ORDER BY rank_change DESC LIMIT 5, one ASC LIMIT 5), each tagged with
      a `direction` column ('climber'/'faller') for color-coding; WHERE clause uses
      `snapshot_date = (SELECT MAX(snapshot_date) ...)` so it stays correct as new days accumulate
      rather than hardcoding a date. Bar chart, X=track_artist, Y=rank_change (diverges naturally above/
      below zero since rank_change is signed), color breakout by `direction`, "show values on data
      points" enabled so each bar displays its exact +/- number. Saved as "KPI 5 - Biggest Movers
      (Climbers & Fallers, Global)".
      KPI 2 (Global vs country) DONE: also native SQL — first KPI needing a self-join (fact_chart_entry
      joined to itself on track_key + date_key, one side filtered to chart_scope='global', the other to
      chart_scope!='global'). Deliberately sorted by `global_rank - country_rank DESC LIMIT 10` to
      surface the BIGGEST mismatches (regional hits hiding inside the data, e.g. Malcolm Todd ranked #50
      globally but #21 in the US) rather than just showing top-global-tracks' country ranks again, which
      would've just repeated the Olivia Rodrigo story from KPI 1/4. Visualized as a scatter plot
      (X=Global Rank, Y=Country Rank) instead of a grouped bar — better fit since this is fundamentally
      a paired-value comparison, and explicitly chosen over bars after direct user feedback ("again a
      bar chart?"). Color-by-track-name caused palette collisions (10 series, ~8-color palette) — tried
      switching the breakout to Country instead (only 4 distinct values, no collisions) but reverted
      after user feedback that it diluted the actual story (individual surprising tracks) in favor of an
      uninteresting country clustering, and broke per-track identification on a static slide. Final fix:
      kept the per-track breakout, manually reassigned colors on the 3 colliding pairs via Metabase's
      color picker. Saved as "KPI 2 - Global vs Country (Biggest Regional Hits)". Note: built directly
      as a Metabase SQL question, not a dedicated dbt model — resolved the open question from the
      Phase 5 design discussion in favor of "Metabase query," now that we know the exact shape needed.
- [x] Assemble all 5 KPIs into one Metabase dashboard
      Single tab (5 charts is a manageable amount for one scrollable page; multiple tabs add presentation
      friction without enough content to justify it). Order: KPI 1 (headline overview) -> KPI 4 (trend) ->
      KPI 5 (star KPI per project plan) -> KPI 2 (most surprising story) -> KPI 3 (supporting context).
      Layout: 2-column grid for KPI 1/4/5/2, KPI 3 widened to full width (24+ genre categories needed
      more horizontal room than half-width gave it). Polish pass: 3 charts (KPI 1, 4, 3) were showing raw
      Postgres join-path labels as axis titles (e.g. "Dim Genre - Genre Key → Genre" instead of "Genre")
      — fixed via each question's Axes tab. KPI 1 switched from vertical Bar to Row chart (horizontal
      bars) after long "Artist — Track" labels didn't fit even after resizing the card — row charts put
      long category names as normal left-aligned text instead of needing rotation, and are arguably the
      more idiomatic chart type for a "Top 10" leaderboard anyway. Possible future polish (not committed
      to, only if time allows): a second dashboard tab for more creative/exploratory views.

### Phase 8 — Docs & demo

- [ ] Finish README (what/why/how + run instructions + screenshots)
- [ ] 1-page architecture diagram
- [ ] Demo script
- [ ] Future-work note

### Session notes (free text — newest at top)

- 2026-06-22: All 5 KPIs complete — Phase 7 dashboard-building (the charts themselves) is done. Backfilled
  today's data first (same cron-asleep pattern as the last 2 days; run_daily_pipeline.sh handled it
  cleanly, 24/24 tests, now 8 days of data). Finished KPI 5 (bar chart, color by direction, "show values
  on data points" for exact numbers on each bar) and built KPI 2 (global vs country) from scratch — see
  Phase 7 checklist above for full detail. KPI 2 highlights: first self-join in the project
  (fact_chart_entry joined to itself on track_key+date_key to compare global vs country rank for the
  same track/day); deliberately sorted for the BIGGEST mismatches instead of top-global-tracks, which
  surfaced a much better story (hidden regional hits like Malcolm Todd — #50 globally, #21 in the US);
  switched from a grouped bar to a scatter plot after direct pushback ("again a bar chart?") since
  scatter is the more correct visualization for a paired-value comparison anyway; tried a country-based
  color breakout to fix a palette collision, reverted after feedback that it diluted the actual story —
  ended up manually fixing only the 3 colliding color pairs instead. Assembled all 5 into one Metabase
  dashboard (single tab, 2-column grid, KPI 3 widened to full width for its 24+ genre categories) — see
  Phase 7 checklist above for the full layout/polish details. Fixed 3 charts showing raw Postgres
  join-path labels as axis titles (e.g. "Dim Date - Date Key → Snapshot Date" instead of "Snapshot
  Date") via each question's Axes tab. Switched KPI 1 from vertical Bar to Row chart — long "Artist —
  Track" labels didn't fit even after resizing, and Row charts handle long category names as normal
  horizontal text instead of needing rotation. **This completes Phase 7 — all 5 KPIs built AND
  assembled into one dashboard.** Per the Build order plan, steps 1-2 (window functions, Metabase) are
  now both done; Phase 6 (GitHub Actions) is next, then Phase 8 (docs). Still on track for the July 1
  checkpoint with room to spare — worth revisiting the Terraform stretch goal once Phase 6 is done.
- 2026-06-21: Continued Phase 7 KPI builds. Mac was asleep again at the 10:15am cron time (confirms
  the conclusion from 6-20: this will keep happening occasionally, manual backfill via
  run_daily_pipeline.sh is the accepted fallback). Ran `./run_daily_pipeline.sh 2026-06-21` — loaded
  today cleanly, 24/24 tests passed with no new data-quality surprises this time. Now at 7 days / 2100
  rows in fact_chart_entry_trends. Built KPI 3 (genre breakdown, saved), KPI 4 (trend over time, saved
  — see session note below for the axis-flip lesson learned), and started KPI 5 (biggest movers) as a
  hand-written SQL question (UNION of top-5-climbers + top-5-fallers) since Metabase's GUI builder
  can't sort+limit in two directions in one question — see Phase 7 checklist above for full details on
  all three. KPI 5 still needs the bar chart + color formatting step, then save. Next: finish KPI 5
  visualization, then KPI 2 (global vs country), then assemble all 5 into an actual Metabase dashboard.
- 2026-06-20: Phase 7 started + a real data-integrity bug found and fixed. Installed Docker, ran
  Metabase via Docker (persistent volume), connected it to local Postgres using host.docker.internal
  (containers can't reach the host via localhost) — all 9 tables visible in Metabase. Before building
  KPIs, discovered local Postgres was stuck at 2026-06-17 (3-day gap) even though S3 had clean data
  through 6-20 — the cloud pipeline was fine, only the local cron bridge (S3 -> Postgres) wasn't firing.
  Backfilled the 3 missing days manually, which surfaced a real dbt test failure once 6 days of data
  existed: 1 duplicate artist_key (Justin Bieber — MusicBrainz returned blank metadata on 6-19 only,
  a transient lookup failure) and 10 duplicate track_key (mostly Olivia Rodrigo tracks — Last.fm
  returns a different track_mbid for the same track on different days). Root cause: dim_artist/
  dim_track used SELECT DISTINCT across ALL columns, so any day-to-day metadata difference for the
  same identity produced two rows colliding on the same surrogate key. Fixed both models: SELECT
  DISTINCT -> GROUP BY identity columns + MAX() on metadata columns — guarantees one row per key AND
  self-heals nulls (MAX ignores NULL, so Justin Bieber's blank 6-19 row gets backfilled from a good
  day). Verified: 24/24 tests passing, Justin Bieber now one clean row with full metadata. Separately
  diagnosed the cron issue with two live test jobs (one writing to home dir, one to the Desktop-based
  project folder) — both succeeded, which rules out the macOS Full Disk Access theory from an earlier
  session; real cause is almost certainly the Mac being asleep at 10:15am (cron doesn't wake a sleeping
  Mac, and a skipped run leaves zero trace). Decided NOT to fight macOS power settings for this —
  occasional manual backfill is an acceptable fallback since the cloud pipeline's SNS email already
  confirms when a day's data is ready in S3. Bigger fix: realized the daily cron job, even when it DID
  fire, never re-ran dbt — so a bad day's data could sit untested indefinitely. Built
  run_daily_pipeline.sh: one script chaining load -> dbt run -> dbt test, used both by cron (no
  argument = today) and manual backfills (date argument = specific day) — tests now run every time
  data is loaded, not just when someone remembers to run dbt by hand. Also added an optional CLI date
  argument to load_to_postgres.py to support this. Built KPI 1 (Top Tracks Now - Global) end-to-end in
  Metabase's visual query builder, step by step in the UI: joined fact_chart_entry to dim_track/
  dim_artist/dim_country/dim_date (inner joins throughout, since relationships tests already guarantee
  matches), filtered to chart_scope=global + snapshot_date=today, sorted by rank ascending, limited to
  10 rows, added a custom column (concat of artist + track name, since neither raw dimension column
  alone identifies a bar) for the X-axis, Playcount as Y-axis. Result: global chart on 2026-06-20 is
  dominated by Olivia Rodrigo (ranks 1-13) — verified this is real data (not a join bug) by cross-
  checking the same query directly in psql. Noted a real, presentation-worthy nuance: bar height
  (playcount) doesn't strictly decrease with rank, because Last.fm's global rank is derived from API
  list order (likely recency/momentum-weighted), not raw cumulative playcount — documented in
  PROJECT_PLAN.md already as "derive rank from list order," now visually confirmed in the dashboard.
  Saved as "KPI 1 - Top Tracks Now (Global)". Started KPI 3 (genre breakdown by country): joins to
  dim_country + dim_genre in progress, not yet filtered/summarized/saved. Next: finish KPI 3 (Summarize
  by count, group by chart_scope + genre, stacked bar), then KPI 4 (trend over time) and KPI 5
  (biggest movers), then circle back to KPI 2 (global vs country) once the shape is clearer.
- 2026-06-18: Conceptual session (no code changes besides docs). Walked through what dbt actually is
  vs. Postgres — dbt is not a database and stores nothing; it only generates and runs SQL against
  Postgres (CREATE TABLE AS SELECT for models, SELECT COUNT(*) checks for tests), then gets out of the
  way. Once `dbt run` finishes, Postgres holds the tables and anything (Metabase, psql, pgAdmin) queries
  them directly with zero dbt involvement — confirmed Metabase will connect straight to Postgres later,
  same as dbt does. Toured the lineage graph via `dbt docs serve` (raw_chart_entries -> stg_chart_entries
  -> 5 dims + fact -> fact_chart_entry_trends). Also added a build-order cross-reference note to
  docs/PROJECT_PLAN.md so it doesn't contradict CLAUDE.md's "Build order plan" (Metabase before GitHub
  Actions, despite Phase numbers running the other way) — committed as "Note build-order reordering...".
  Assessed KPI feasibility against current tables ahead of Phase 7: 4 of 5 KPIs (#1 top tracks, #3 genre
  breakdown, #4 trend over time, #5 biggest movers) are answerable directly off fact_chart_entry /
  fact_chart_entry_trends with simple filter/group-by queries. KPI #2 ("global vs country") is the one
  exception — it compares two different ROWS to each other (global row vs. country row, same track, same
  day) rather than aggregating, so it needs a self-join; decided (reconfirmed) to design that as a small
  dedicated dbt model once we're actually in Metabase and know the exact shape needed, not before.
  Addressed a depth/complexity worry: recommended finishing the basics (Phase 7 Metabase, Phase 6 GitHub
  Actions, Phase 8 docs) before revisiting Terraform/Snowflake, per the existing July 1 checkpoint trigger
  — reframed that the project already has real depth (star schema, surrogate keys, multi-source enrichment,
  window functions, 24 tests) independent of infra tooling. Pace estimate given: ~4 more sessions to
  finish the basics (2 for Metabase, 1 for GitHub Actions, 1 for Phase 8 docs), comfortably inside the
  July 1 checkpoint and July 10 presentation date. Next: Phase 7 — Metabase (Docker install, connect to
  Postgres, build KPIs #1/#3/#4/#5 first, then design the KPI #2 self-join model).
- 2026-06-18: Window functions built. New model fact_chart_entry_trends.sql joins fact_chart_entry to
  dim_date (for real chronological ordering — date_key is just a hash, doesn't sort), then uses
  LAG(rank) partitioned by track_key+country_key ordered by snapshot_date to get each track's previous
  rank in that same chart. rank_change = previous_rank - rank (positive = climbed, negative = fell);
  NULL on a track's first-ever appearance in a chart (no prior value to compare to) — expected, not a
  bug. 900 rows, 10/10 new tests passing (24/24 total across the project). Spot-checked top movers in
  psql — logic confirmed correct (e.g. rank 42 -> 26 showed rank_change = +16). This closes Phase 5.
  Also clarified a scope question: user asked about comparing a track's global rank to its rank in its
  origin country — this is KPI #2 "Global vs country" in PROJECT_PLAN.md, a DIFFERENT comparison from
  rank_change (same chart over time vs. same day across charts). Decided to defer building it until
  Phase 7 (Metabase), where we'll know the exact shape the dashboard needs before deciding if it
  warrants its own dbt model or can be a direct query. Next: Phase 7 — Metabase dashboard.
- 2026-06-18: Build order planning session. Compared architecture against a classmate's project (they use Terraform IaC + Airflow orchestrating dbt in Docker + Snowflake as primary warehouse + CI/CD that deploys infra). Assessment: their project leans more into platform/DevOps maturity; ours leans more into data modeling depth (real star schema with surrogate keys + 14 passing tests vs. their less clear dimensional modeling). Decided NOT to add Airflow or switch to Snowflake-primary — out of scope and not worth the risk this close to presentation. DID decide to add Terraform as a stretch goal (see "Build order plan" section above) since it's a contained, low-risk addition via `terraform import` (adopts existing resources, no rebuild). Presentation date confirmed as July 10, 2026 — user wants a polished, fully-working project by end of first week of July. Settled priority order: window functions -> Phase 7 (Metabase) -> Phase 6 (GitHub Actions) -> Phase 8 (docs) -> Terraform only if time remains before ~July 1. Next: build dbt window functions for rank_change / biggest movers.
- 2026-06-17: Phase 5 star schema complete. Built all 5 dimensions (dim_artist, dim_country, dim_date, dim_genre, dim_track) and fact_chart_entry in models/marts/. Surrogate keys generated via md5() hash of natural keys (e.g. md5(artist_name || '-' || artist_mbid)) — deterministic so keys stay stable across reruns, unlike ROW_NUMBER(). fact_chart_entry built by recomputing the same hash inline (no joins needed since md5 is deterministic) — 900 rows = 3 daily snapshots x 300 rows, confirming no rows lost/duplicated. 14 dbt tests passing: unique+not_null on dim_artist.artist_key and dim_track.track_key, not_null+relationships on all 5 fact foreign keys. Verified lineage visually with dbt docs generate + serve — raw_chart_entries -> stg_chart_entries -> 5 dims + fact, exactly as designed. Remaining Phase 5 stretch: window functions for rank_change/biggest movers (useful for KPIs, not yet built). Next: decide whether to build window functions now or move to Phase 6 (GitHub Actions) / Phase 7 (Metabase).
- 2026-06-17: Cron cleanup. The 8:15am S3-loader cron job silently didn't fire (no log entry) — likely Mac asleep or Full Disk Access not fully effective yet. Moved it to 10:15am (after the 8:00am cloud pipeline has plenty of time to finish) and confirmed by running it manually: 300 rows loaded for 2026-06-17. Also removed the old 10:00am `run_pipeline.sh` cron job — it was the pre-cloud full local pipeline (fetch + enrich locally) and is now redundant since Glue does that in AWS; it was silently duplicating API calls (harmless due to the duplicate-date guard, but wasteful). Current automation: 8:00am EventBridge → Step Functions → Glue fetch → Glue enrich → S3 clean file → email notification; 10:15am local cron → load_to_postgres.py pulls that S3 file into Postgres. Only one local cron job remains.
- 2026-06-16: Phase 5 started. dbt-postgres 1.8.2 installed, project initialized (music_charts/), connected to local Postgres. Staging layer complete: sources.yml points at raw_chart_entries, stg_chart_entries.sql casts types + cleans nulls. dbt_project.yml updated: staging=view, marts=table. Next: dimension tables then fact_chart_entry.
- 2026-06-16: Phase 4 complete. Step Functions state machine (music-charts-pipeline) chains Job #1 → Job #2 with retries and a Fail state. EventBridge schedule fires daily at 8:00am Berlin time. SNS topic (music-charts-notifications) + Lambda function (music-charts-notify) send success/failure email — tested and confirmed working. Local loader updated: load_to_postgres.py now has load_from_s3() that pulls clean S3 file into Postgres; cron job at 8:15am runs it daily. IAM note: oront is the console user (UI work), terra_proj is the programmatic user (API keys/CLI). Terminal granted Full Disk Access so cron jobs fire. Next: Phase 5 — dbt star schema.
- 2026-06-15: Phase 3 complete. Both Glue jobs running in cloud. IAM hurdles: needed AWSGlueConsoleFullAccess + iam:PassRole inline policy + Glue role must be named AWSGlueServiceRole-* for PassRole to work. Decision: create jobs via UI, verify via CLI. Job #1 (music-charts-fetch): fetches Last.fm → raw/YYYY-MM-DD/ in S3, runs in ~20s. Job #2 (music-charts-enrich): reads raw S3, adds genre + MusicBrainz → clean/YYYY-MM-DD/ in S3, runs in ~2.5min. Job #2 initial failure: missing --S3_BUCKET parameter (not saved in job config). Next: Phase 4 — Step Functions orchestration.
- 2026-06-15: Phase 2b complete. Built src/musicbrainz.py (1.1s rate limit, retries, _empty_result fallback). Added artist_mbid to pipeline rows. 4 new columns: artist_origin_country, artist_type, artist_gender, artist_begin_year. 291/300 rows have origin country. Genre unknown rate: 119/300 — documented limitation (80% of unknowns have zero tags, concentrated in non-Western country charts). load_to_postgres.py rewritten to APPEND with duplicate guard (checks snapshot_date before loading). First daily snapshot loaded: 2026-06-15, 300 rows in raw_chart_entries. Daily automation: cron job set to 10:00am via run_pipeline.sh — shows Mac desktop notification on success or failure. pipeline.log captures all output. AWS budget cap: $20 max, billing alerts at $10 and $20 to be set as first step of Phase 3. Next: Phase 3 — AWS Glue.
- 2026-06-12: Phase 2b decided — MusicBrainz enrichment is GO (not optional). Pre-flight checks showed 97% artist MBID coverage from Last.fm; MusicBrainz sample (15 artists) had 100% country/type/begin_year, 73% gender (groups have no gender — expected). Join key: artist MBID. Will add artist_mbid column to pipeline.py, build src/musicbrainz.py client, cache results to avoid repeat lookups.
- 2026-06-11: Phase 2 complete. pipeline.py fetches global + 5 countries, enriches with genre, runs quality checks, saves charts_clean.csv (300 rows, 50 per chart). Country ranks were 0-based — fixed to 1-based (+1). playcount/listeners null for all country rows (expected, geo endpoint doesn't return them). 79/300 rows unknown genre (expected — junk tags or no tags). Added explanatory WHY comments to both src/lastfm.py and pipeline.py. Created docs/PRESENTATION_NOTES.md as a running presentation reference — update it every session. Warehouse decision: Postgres primary, Snowflake added later at Phase 5 as second dbt target — do NOT start trial yet. Next: Phase 3 — move code into AWS Glue.
- 2026-06-10: Completed Phase 0 (except Docker, deferred to Phase 7) and Phase 1. GitHub repo connected, venv + requirements.txt created, Postgres db music_charts ready, S3 bucket music-charts-pipeline-orontavor created, Last.fm API key in .env. fetch_global.py fetches 50 global tracks to CSV; load_to_postgres.py loads CSV into raw_global_chart table — confirmed rows visible in pgAdmin. Next: Phase 2 — add countries, genre enrichment, combine into tidy table.

### Open questions

- [ ] Ask instructors: is AWS ingestion + local Postgres warehouse OK for BYOP, or do they require a cloud warehouse / Terraform / Airflow?
- [ ] Confirm with instructors: sharing Last.fm as a public API with a classmate (different project) is fine.
- [ ] Confirm: solo or team project?

### Warehouse decision (SETTLED 2026-06-11)
Postgres is PRIMARY and guaranteed — build everything against local Postgres first
(free, no clock). It is the can't-fail submission.
Snowflake is a BACKUP / bonus cloud layer, added LATER as a SECOND dbt target (same
models, swap the connection profile — dbt is warehouse-agnostic). If Snowflake works,
demo the cloud version; if the trial lapses or breaks, fall back to Postgres instantly.
- DO NOT create the Snowflake trial yet. It's only needed at Phase 5 (Week 3).
- Trial created: 2026-06-16. Estimated expiry: 2026-07-16 (30 days). That's 5 days after
  the July 11 presentation — acceptable buffer. Edition: Standard.
- Portfolio line: "warehouse-agnostic dbt project — runs on local Postgres or cloud Snowflake
  by switching the target."

## How to resume after a break / lost chat

Open this folder in VS Code, open Claude Code, and say: "Read CLAUDE.md and docs/PROJECT_PLAN.md, check the Progress log, and tell me where we left off and what the next step is. Don't build anything yet." Also run git log --oneline to see what's already committed.
