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
