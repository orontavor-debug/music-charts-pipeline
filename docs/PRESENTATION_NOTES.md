# Presentation Notes — Music Charts Pipeline

This file is a running log of decisions made, hurdles encountered, and the reasoning
behind technical choices. Updated every session. Use it to build your final presentation.

---

## What this project is (one sentence)

An automated data pipeline that fetches daily music chart data from the Last.fm API —
globally and for 5 countries — enriches it with genre, stores it in the cloud (AWS S3),
loads it into a local Postgres warehouse, models it as a star schema with dbt, and
displays trend KPIs in a Metabase dashboard.

---

## The tech stack and why each tool was chosen

| Tool | Role | Why chosen |
|---|---|---|
| Python + pandas | Fetch, clean, combine data | Industry standard for data engineering |
| Last.fm API | Data source | Free, no OAuth, verified working |
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
- **Unknown genre count** — informational; 79/300 is expected and acceptable

---

## Session log (newest first)

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
