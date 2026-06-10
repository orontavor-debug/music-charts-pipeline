# Capstone Project Plan — Music Charts Trend Analytics Pipeline (Last.fm)

**Project path:** Bring Your Own Project (BYOP)
**Duration:** 4 weeks · **Complexity:** medium (close to the school's example projects)

> All data points have been VERIFIED against the live Last.fm API.
> Fields are labeled FETCHED (returned by the API) or DERIVED (we compute it).
>
> WAREHOUSE: LOCAL PostgreSQL (not Snowflake). Reason: Snowflake's free trial is
> only 30 days, which doesn't fit a 4-week project. Postgres is free forever and
> already installed (pgAdmin). dbt + Metabase both support it fully. We KEEP all
> AWS cloud pieces (Glue, S3, Step Functions, Lambda/SNS) so the project still
> demonstrates cloud ingestion + orchestration, matching the example projects.
>
> GEO IS CORE: we fetch per-country charts for 5 countries every snapshot. This is
> a data-engineering project, so the country dimension is here to add real ingestion
> volume, a star-schema modeling exercise, and a genuine cross-source join — not for
> BI polish.

---

## 1. The big picture (plain words)
We build an automated data pipeline. It grabs live music chart data from the Last.fm
API — both the GLOBAL chart and the TOP CHART FOR 5 COUNTRIES — cleans and enriches it
(adds genre), stores it in AWS S3, loads it into a local Postgres warehouse, models it
into a star schema with dbt, and shows trends on a Metabase dashboard. It runs daily and
saves a dated snapshot, so over time we see what's rising, falling, and trending — globally
and per country.

Flow: Last.fm (global + 5 countries) -> Python (in AWS Glue) -> AWS S3 -> local loader -> Postgres -> dbt (star schema) -> Metabase.

## 2. Business context (why anyone cares)
For a music label, distributor, or marketing team: what's hot right now and IN WHICH
COUNTRIES, which genres dominate where, which tracks are climbing fast (early hit signals),
and where a track is breaking first. Comparing global vs per-country charts shows whether
something is a worldwide hit or a regional one — useful for targeting promotion and ad spend
by market. This "watch the trend, act early, by region" thinking maps to online marketing.

One sentence: *we turn raw, scattered music-popularity data from multiple countries into a
modeled warehouse and dashboard that show what's trending, where, and what's gaining momentum.*

## 3. What we fetch (the data) — VERIFIED against the API
Source: Last.fm API — https://www.last.fm/api (free; needs a free API key, no OAuth).
Get a key: https://www.last.fm/api/account/create
Base URL: https://ws.audioscrobbler.com/2.0/  ·  Add &format=json to every call.

Endpoints we use:

- **chart.getTopTracks** — GLOBAL top tracks now. One of two spines.
  Returns per track (VERIFIED): name, playcount, listeners, mbid, url, nested artist (name+mbid).
  Does NOT return a rank number -> we DERIVE rank from list position (1st = rank 1).

- **geo.getTopTracks** — top tracks PER COUNTRY. The other spine. CORE to this project.
  Param: country = an ISO 3166-1 country NAME (e.g. "united states", "germany"). Required.
  We call it once per country for our 5 countries.
  Returns per track (VERIFIED): name, playcount, mbid, url, nested artist (name+mbid),
  AND an explicit rank attribute (country charts DO include rank — so rank is FETCHED here).
  IMPORTANT: the track-level mbid is OFTEN EMPTY in geo results (only the artist mbid is
  reliably present) -> joins to the global chart must fall back to name matching.
  TIME WINDOW: geo is "most popular LAST WEEK by country", while chart.getTopTracks is "now".
  So the global and country layers cover slightly different windows — documented, not a bug.

- **chart.getTopArtists** — global top artists now (optional extra spine).
  Returns per artist (VERIFIED): name, playcount, listeners, mbid, url.

- **track.getTopTags** (or track.getInfo) — the GENRE source.
  Last.fm has NO "genre" field. It returns crowd "tags" (e.g. "pop","rock","indie").
  We fetch tags per track and take the top music tag as the genre. Tags are messy:
  some are non-genre ("seen live","favorites"), some tracks have none -> filter junk,
  default to "unknown".

THE 5 COUNTRIES: United States, United Kingdom, Germany, Brazil, Japan.
(Chosen for varied musical cultures — Western/English, European, Latin American, East Asian —
so the cross-country comparison is analytically meaningful.)

**History note:** charts show "now"/"last week", not downloadable day-by-day history. Our
pipeline builds history by snapshotting daily with the date stamped on each row. KPIs that
need time fill in as snapshots accumulate. (No synthetic dates; each row timestamped at capture.)

## 4. Data model — STAR SCHEMA (the modeling exercise)
Because geo is core, we model dimensionally rather than as one flat table.

FACT table — `fact_chart_entry` (grain: one track, on one chart, on one snapshot date):
| Column | Source | F/D | Meaning |
|---|---|---|---|
| snapshot_date | pipeline | D | day captured |
| chart_scope | pipeline | D | 'global' or a country name |
| rank | global: list position / geo: rank attr | global=DERIVED, geo=FETCHED | chart position |
| track_key | join to dim_track | D | link to track dimension |
| artist_key | join to dim_artist | D | link to artist dimension |
| country_key | join to dim_country | D | link to country dimension ('global' allowed) |
| date_key | join to dim_date | D | link to date dimension |
| playcount | chart/geo | F | total plays |
| listeners | chart (global only) | F | unique listeners (geo doesn't return listeners) |
| rank_change | dbt | D | vs previous snapshot (window function) |
| is_new_entry | dbt | D | new on this chart this snapshot |

DIMENSIONS:
- `dim_track`: track_key, track_name, mbid (may be empty), first_seen_date
- `dim_artist`: artist_key, artist_name, artist_mbid
- `dim_genre`: genre_key, genre_tag (from track.getTopTags, cleaned)  [a track links to its top genre]
- `dim_country`: country_key, country_name (the 5 + 'global')
- `dim_date`: date_key, calendar date, day/week/month

Note: listeners is only on the GLOBAL chart, not geo — so that column is null for country rows.
That's a real, documented difference between the two sources, handled in staging.

## 5. The KPIs (dashboard) — country comparison is now first-class
1. **Top tracks & artists now** — global chart leaders (ranked bar).
2. **Global vs country** — same track's rank globally vs in each of the 5 countries (grouped bar).
   "Is this a worldwide hit or a regional one?"
3. **Genre breakdown by country** — which genres dominate in US vs Japan vs Brazil etc. (stacked bar).
4. **Trend over time** — ranks across daily snapshots, filterable by country (line). Fills in over days.
5. **Biggest movers (momentum)** — fastest climbers since last snapshot, global or per country (bar). Star KPI.

KPIs 1-3 work from a single snapshot (day one). KPIs 4-5 fill in as snapshots accumulate.

## 6. Tools (plain words)
- **Python** — language for fetch + clean code.
- **pandas** — tables of data in code (like Excel, in Python).
- **AWS S3** — cloud storage; where we drop cleaned files.
- **AWS Glue** — runs our Python in the cloud. A real DE service.
- **AWS Step Functions** — orchestrator; runs Glue jobs in order, with retries.
- **AWS Lambda + SNS** — tiny function that sends a success/failure notification.
- **PostgreSQL (local)** — the warehouse. Free, installed (pgAdmin). Holds raw + star-schema tables.
- **dbt (dbt-postgres adapter)** — builds the star schema with SQL (raw -> staging -> marts).
- **GitHub Actions** — CI/CD; auto-runs dbt tests on push.
- **Metabase** — free dashboard (Docker, local), reads Postgres.
- **Git / GitHub** — version control.

Left out (future work): Terraform, Airflow, QuickSight, and a cloud warehouse
(local Postgres used instead; production cloud version would be Snowflake/BigQuery reading S3).

## 7. Architecture / data flow
```
Step Functions (daily, orchestrates)
  -> Glue Job #1 "Fetch"  -> Last.fm GLOBAL chart + LOOP over 5 countries (geo) -> raw files in S3 (raw/)
  -> Glue Job #2 "Enrich/flatten" -> add genre (tags), clean, derive global rank,
                                     combine global + 5 countries -> tidy file in S3 (clean/)
  -> Lambda + SNS  -> success/failure notification

Local loader (Python on my machine)
  -> reads the clean file from S3 -> writes into local Postgres (raw table)

  -> dbt      -> raw -> staging -> STAR SCHEMA marts (fact + 5 dims; rank_change via window fns)
  -> Metabase -> reads Postgres, shows the 5 KPIs

GitHub Actions: on push -> auto-run dbt tests (CI/CD)
```
Why a local loader: local Postgres isn't reachable from AWS, so a small local Python script
pulls the clean file from S3 and writes it into Postgres (pandas read S3 -> to_sql). This
replaces Snowflake's "external stage". Deliberate, documented choice.

INGESTION VOLUME (per daily run): 1 global call + 5 country calls + ~50 genre-enrichment
calls (one per global track; reuse/cache for country tracks where possible). Well within
rate limits IF we pause politely between calls. Watch for API error 29 = rate limit exceeded.

## 8. How data is combined (joins, simply)
- Global chart + each country chart -> stacked into the fact table, tagged by chart_scope.
- Genre: fetch tags per track via track.getTopTags, take top music tag, attach on track+artist.
- Matching the SAME track across global and country charts: prefer mbid, BUT geo track mbid is
  often empty -> fall back to normalized track_name + artist_name (lowercase, trim).
- Count matched vs unmatched rows after each join (data-quality check) to catch problems early.
This cross-chart, mixed-key matching is real entity-resolution work — core data engineering.

## 9. Plan of work (phases)
**Phase 0 — Setup:** GitHub repo + README; Python venv + requirements.txt; confirm local Postgres (pgAdmin); AWS account + S3 bucket; Last.fm API key; install Docker (Metabase).
**Phase 1 — Thin slice (local):** fetch GLOBAL chart once -> file -> load into Postgres by hand -> see rows. Proves the path. No geo/genre/Glue yet.
**Phase 2 — Python fetch + clean (local):** API client (requests, retries, rate-limit pauses); derive global rank; LOOP over 5 countries (geo); enrichment loop (tags->genre); pandas combine global+countries into the tidy table; quality checks (matched-row counts).
**Phase 3 — Move code into AWS Glue:** Python into Glue (Job #1 fetch global+5 countries, Job #2 enrich/flatten), writing to S3; IAM permissions (the fiddly bit — go slow).
**Phase 4 — Orchestrate (Step Functions + Lambda/SNS):** Job #1 then #2 with retries; Lambda->SNS notification; schedule daily; add the local loader (S3 -> Postgres).
**Phase 5 — dbt star schema (Postgres):** dbt-postgres; sources -> staging -> marts (fact_chart_entry + dim_track/artist/genre/country/date); window functions (rank_change, movers); tests + docs/lineage.
**Phase 6 — GitHub Actions:** workflow that runs dbt tests on push (stretch: upload Glue script to S3).
**Phase 7 — Dashboard:** Metabase via Docker -> connect to Postgres -> build the 5 KPIs.
**Phase 8 — Docs & demo:** README (what/why/how + run + screenshots); 1-page architecture diagram; demo script; future-work note.

## 10. Week-by-week (4 weeks)
- **Week 1:** Phases 0-1 (setup + thin slice). Start daily snapshots ASAP. Deliver README skeleton + architecture diagram.
- **Week 2:** Phases 2-4 (Python with geo + Glue + Step Functions + local loader). Deliver cloud ingestion + S3 + Postgres screenshots.
- **Week 3:** Phases 5-6 (dbt star schema + GitHub Actions). Deliver models + tests + lineage + CI workflow.
- **Week 4:** Phases 7-8 (dashboard + docs + demo). Deliver Metabase dashboard + final README + demo script.
Rule: every week ends with PROOF (screenshots, logs, lineage, dashboard).

## 11. Risks & mitigations
- More API calls now (global + 5 countries + genre loop) -> pause between calls, cache genre
  lookups, limit tracks per chart (~50); handle error 29 (rate limit) with backoff.
- geo track mbid often empty -> name-matching fallback (normalized text); count matches.
- geo is "last week" vs global "now" -> documented; don't claim perfect time alignment.
- listeners missing on geo -> null for country rows; handled in staging, not a bug.
- AWS IAM permissions fiddly -> go slow in Phase 3, test one piece at a time (main time sink).
- Cost: S3 ~free; Glue + Step Functions a few cents; Postgres free. Keep data tiny.
- Local Postgres unreachable from AWS -> local loader from S3 (documented).
- Time series needs days -> start daily runs Week 1; KPIs 1-3 work immediately.
- Genre tags messy/empty -> filter junk, default "unknown".
- Scope creep -> global spine works even if geo/Glue fight you; can fall back to local Python -> Postgres.

## 12. Definition of done
- Data flows Last.fm (global + 5 countries) -> Glue -> S3 -> local loader -> Postgres -> dbt -> Metabase
- Step Functions runs Glue jobs daily with SNS notification
- GitHub Actions runs dbt tests
- dbt STAR SCHEMA (fact + 5 dims) with tests + lineage
- Metabase dashboard with the 5 KPIs (incl. country comparison)
- README + 1-page architecture diagram + demo script
- No secrets in code (env vars / GitHub Secrets)

## 13. vs. the school's example projects
Examples = API -> Glue -> S3 -> Snowflake -> dbt (star schema) -> dashboard, wrapped in
Terraform + GitHub Actions + Step Functions + Lambda/SNS + Airflow + QuickSight.
This plan matches: the backbone, Glue ingestion (now multi-country), S3, Step Functions,
Lambda/SNS, a dbt STAR SCHEMA, and a CI/CD workflow. It simplifies: local Postgres (not
Snowflake), Metabase (not QuickSight), no full Terraform, Step Functions/GitHub Actions
instead of Airflow. Result: clearly "medium", same shape, finishable in 4 weeks, free.

Honest portfolio note: AWS-ingestion + local-Postgres-warehouse is a deliberate hybrid to
keep the project free and dodge Snowflake's 30-day trial, while still demonstrating cloud
ingestion, multi-source fan-out (5 countries), star-schema modeling, and orchestration.
Production cloud version would swap Postgres for a cloud warehouse reading directly from S3.

Open question for instructors: *"For BYOP, is AWS ingestion + local Postgres warehouse
acceptable, or do you require a cloud warehouse and/or Terraform + Airflow specifically?"*
