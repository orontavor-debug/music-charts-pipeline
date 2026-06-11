# CLAUDE.md — Project Briefing

This file orients you (Claude Code) at the start of every session. Read it first, then read docs/PROJECT\_PLAN.md for full detail.

## STANDING INSTRUCTIONS (do these automatically, every session)

1. At the START of a session: read the "Progress log" section below and tell me where we left off and what the next step is.  
2. As we COMPLETE things: keep the Progress log accurate (mark items done, move the \[\~\] in-progress marker, add a short "Session notes" line).  
3. Near the END of a session, or whenever I say I'm stopping: remind me, and update the Progress log yourself before we finish — don't wait for me to remember.  
4. After finishing a meaningful piece, suggest a git commit with a clear message. These keep the project's memory in the files, so we never lose our place if the chat history resets.

## What this project is

A data-engineering capstone: an automated pipeline that fetches live music chart data from the Last.fm API — the GLOBAL chart PLUS the top chart for 5 countries (United States, United Kingdom, Germany, Brazil, Japan) — cleans and enriches it (adds genre) with Python, stores it in AWS S3, loads it into a LOCAL Postgres warehouse, models it as a STAR SCHEMA with dbt, and shows trend KPIs in a Metabase dashboard. It runs daily and builds up a time series so we can see what's rising, falling, and trending — globally and per country.

The geo/country layer is CORE (not optional): it adds real ingestion volume (loop over 5 countries), a star-schema modeling exercise (fact \+ track/artist/genre/ country/date dimensions), and a genuine cross-chart join. This is a data-engineering project, so that pipeline substance is the point — not BI polish.

The full plan (business context, data source, schema, KPIs, phases, tools) is in: docs/PROJECT\_PLAN.md Always consult it before building. It is the source of truth.

Note: the data fields in the plan have been verified against the live Last.fm API. The plan marks each column as FETCHED (returned by the API) or DERIVED (we compute it). Key things to remember:

- The GLOBAL chart (chart.getTopTracks) does NOT return a rank number \-\> derive it from list order.  
- The COUNTRY charts (geo.getTopTracks) DO return a rank attribute \-\> rank is fetched there.  
- geo.getTopTracks takes country \= an ISO country NAME (e.g. "united states", "germany").  
- geo track-level mbid is OFTEN EMPTY \-\> joins to the global chart fall back to name matching.  
- geo is "most popular LAST WEEK"; global is "now" \-\> slightly different time windows (documented).  
- geo returns no "listeners" field (global does) \-\> listeners is null for country rows.  
- "genre" comes from crowd "tags" (top tag, needs cleaning), not a genre field.  
- The 5 countries: United States, United Kingdom, Germany, Brazil, Japan.

## Tech stack

- Python \+ pandas (fetching \+ cleaning)  
- AWS S3 (cloud storage), AWS Glue (runs our code in cloud), AWS Step Functions (orchestration), AWS Lambda \+ SNS (notifications)  
- PostgreSQL (LOCAL) as the warehouse — NOT Snowflake. Reason: Snowflake's free trial is only 30 days, which doesn't fit a 4-week project. Postgres is free forever and already installed locally (pgAdmin). We KEEP all the AWS pieces so the cloud-ingestion skills are still demonstrated.  
- dbt (dbt-postgres adapter) — SQL transformations, runs against local Postgres  
- GitHub Actions (CI/CD — auto-runs dbt tests)  
- Metabase (dashboard, runs locally via Docker, connects to Postgres)  
- Git/GitHub (version control)

IMPORTANT loader detail: AWS can't reach the local Postgres, so a small local Python script pulls the clean file down from S3 and writes it into Postgres (pandas read from S3 \-\> to\_sql into Postgres). This replaces Snowflake's "external stage" step.

## Build strategy — IMPORTANT

Build LOCAL-FIRST, then lift to the cloud.

1. Get the whole pipeline working on my laptop first (Python \-\> file \-\> local Postgres \-\> dbt \-\> Metabase). S3 comes in when we move to Glue.  
2. ONLY THEN move the Python into AWS Glue \+ Step Functions as an upgrade layer. Reason: I always want a working version. If the cloud pieces fight me near a deadline, the local version is still a complete, submittable project.

## About me (the developer) — please respect this

- I am a rookie / beginner with most of this stack. Go step by step.  
- I want to LEARN, not just receive finished code. A goal of this project is to be able to explain the code in job interviews.  
- So: build in SMALL steps. After writing something, briefly explain what it does and why. Don't autopilot through many steps at once.  
- Check in with me before big moves (installing things, creating many files, anything that costs money on AWS).  
- Prefer the simplest thing that works. Avoid cleverness I won't understand.  
- If I seem confused, slow down and explain in plain words.

## Money / safety notes

- Keep AWS usage tiny. S3 is \~free; Glue \+ Step Functions cost a few cents — fine, but never run large jobs. Warn me before anything that could cost more.  
- NO secrets (API keys, passwords) in code or git. Use a .env file (git-ignored) or environment variables. Remind me if I'm about to commit a secret.

## Progress log — UPDATE THIS EVERY SESSION

This is the project's memory. At the START of each session, read this to see where we left off. At the END of each session, update it (mark items DONE, note what's IN PROGRESS and what's NEXT). This way any fresh Claude Code session can pick up exactly where we stopped, even if the chat history is gone.

Status key: \[ \] todo · \[\~\] in progress · \[x\] done

### Phase 0 — Setup

- [x] Create GitHub repo \+ README skeleton  
- [x] Python virtual environment \+ requirements.txt  
- [x] Confirm local Postgres works (pgAdmin) — db: music_charts, user: orontavor, port: 5432  
- [x] Create AWS account \+ an S3 bucket — bucket: music-charts-pipeline-orontavor  
- [x] Get Last.fm API key (store in .env, NOT in code)  
- [ ] Install Docker (for Metabase later — can wait)

### Phase 1 — Thin slice (local)

- [x] Python: fetch GLOBAL chart once, save to a file  
- [x] Load that file into Postgres by hand  
- [x] See the rows in Postgres (pgAdmin) — proves the path end to end

### Phase 2 — Python fetch \+ clean (local)

- [ ] API client (requests wrapper, timeout, retries, rate-limit pause)  
- [ ] Derive global rank from list order  
- [ ] Loop over the 5 countries (geo.getTopTracks)  
- [ ] Enrichment loop: genre per track (track.getTopTags), clean tags  
- [ ] pandas: combine global \+ 5 countries into the tidy table  
- [ ] Quality checks (no nulls/dupes; count matched rows after joins)

### Phase 3 — Move code into AWS Glue

- [ ] Glue Job \#1 "Fetch" (global \+ 5 countries) \-\> S3 raw/  
- [ ] Glue Job \#2 "Enrich/flatten" \-\> S3 clean/  
- [ ] IAM permissions (go slow, test one piece at a time)

### Phase 4 — Orchestrate (Step Functions \+ Lambda/SNS)

- [ ] Step Functions: run Job \#1 then \#2 with retries  
- [ ] Lambda \+ SNS success/failure notification  
- [ ] Schedule daily  
- [ ] Local loader: pull clean file from S3 \-\> write into Postgres

### Phase 5 — dbt star schema (Postgres)

- [ ] dbt-postgres set up \+ connected  
- [ ] sources \-\> staging \-\> marts (fact\_chart\_entry \+ 5 dims)  
- [ ] window functions (rank\_change, biggest movers)  
- [ ] dbt tests \+ docs/lineage

### Phase 6 — GitHub Actions

- [ ] Workflow that runs dbt tests on push

### Phase 7 — Dashboard (Metabase)

- [ ] Metabase via Docker, connected to Postgres  
- [ ] Build the 5 KPIs

### Phase 8 — Docs & demo

- [ ] Finish README (what/why/how \+ run instructions \+ screenshots)  
- [ ] 1-page architecture diagram  
- [ ] Demo script  
- [ ] Future-work note

### Session notes (free text — newest at top)

- 2026-06-10: Completed Phase 0 (except Docker, deferred to Phase 7) and Phase 1. GitHub repo connected, venv + requirements.txt created, Postgres db music_charts ready, S3 bucket music-charts-pipeline-orontavor created, Last.fm API key in .env. fetch_global.py fetches 50 global tracks to CSV; load_to_postgres.py loads CSV into raw_global_chart table — confirmed rows visible in pgAdmin. Considering Snowflake (user will create account 2026-06-11 — trial ends 2026-07-11, same day as submission). Next: Phase 2 — add countries, genre enrichment, combine into tidy table.

### Open questions

- [ ] Ask instructors: is AWS ingestion \+ local Postgres warehouse OK for BYOP, or do they require a cloud warehouse / Terraform / Airflow?  
- [ ] Confirm with instructors: sharing Last.fm as a public API with a classmate (different project) is fine.  
- [ ] Confirm: solo or team project?

## How to resume after a break / lost chat

Open this folder in VS Code, open Claude Code, and say: "Read CLAUDE.md and docs/PROJECT\_PLAN.md, check the Progress log, and tell me where we left off and what the next step is. Don't build anything yet." Also run git log \--oneline to see what's already committed.  
