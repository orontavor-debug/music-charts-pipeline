# Music Charts Pipeline

An automated data engineering pipeline that tracks daily music chart trends globally and across 5 countries.

## What it does

Fetches the Last.fm global chart and top charts for the United States, United Kingdom, Germany, Brazil, and Japan every day. Enriches each track with genre (from Last.fm crowd tags) and artist metadata (from MusicBrainz: origin country, type, gender, formation year). Stores everything in AWS S3, loads it into a local Postgres warehouse, models it as a star schema with dbt, and displays trend KPIs in a Metabase dashboard.

## Tech stack

| Layer | Tool |
|---|---|
| Data sources | Last.fm API, MusicBrainz API |
| Cloud ingestion | AWS Glue (Python Shell jobs) |
| Orchestration | AWS Step Functions + EventBridge |
| Notifications | AWS Lambda + SNS |
| Cloud storage | AWS S3 |
| Warehouse | PostgreSQL (local) |
| Transformation | dbt (dbt-postgres) |
| CI/CD | GitHub Actions |
| Dashboard | Metabase (Docker) |

## Pipeline architecture

```
Last.fm API ──┐
              ├──► Glue Job #1 (fetch) ──► S3 raw/
MusicBrainz ──┘         │
                         ▼
                  Glue Job #2 (enrich) ──► S3 clean/
                         │
                    Step Functions
                    (daily 8am CET)
                         │
                  local loader script ──► Postgres ──► dbt ──► Metabase
```

## Data collected

- 300 rows per daily snapshot (50 tracks × 6 charts)
- Global chart + United States, United Kingdom, Germany, Brazil, Japan
- Fields: track name, artist, rank, genre, playcount, listeners, artist origin country, artist type, artist gender, formation year

## Project status

- ✅ Phase 0 — Setup
- ✅ Phase 1 — Thin slice (local end-to-end)
- ✅ Phase 2 — Full fetch + genre enrichment
- ✅ Phase 2b — MusicBrainz artist enrichment
- ✅ Phase 3 — AWS Glue cloud ingestion
- ✅ Phase 4 — Step Functions orchestration + notifications
- 🔄 Phase 5 — dbt star schema
- ⬜ Phase 6 — GitHub Actions CI/CD
- ⬜ Phase 7 — Metabase dashboard
- ⬜ Phase 8 — Docs & demo
