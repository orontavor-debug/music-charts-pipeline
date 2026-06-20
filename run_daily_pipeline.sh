#!/bin/bash
set -e

PROJECT_DIR="/Users/orontavor/Desktop/bootcamp/music-charts-pipeline"
cd "$PROJECT_DIR"

# Load raw data from S3 into Postgres. Pass a date (YYYY-MM-DD) as $1 to
# backfill a specific day; omit it to load today's date (the daily cron job
# calls this with no argument).
venv/bin/python load_to_postgres.py "$@"

# Rebuild the star schema and run all data-quality tests against whatever
# is now in Postgres. Runs every time, whether triggered by cron or a
# manual backfill, so a bad day's data never sits untested.
cd "$PROJECT_DIR/music_charts"
"$PROJECT_DIR/venv/bin/dbt" run
"$PROJECT_DIR/venv/bin/dbt" test
