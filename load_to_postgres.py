import io
import os
from datetime import date
import boto3
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DB_USER = "orontavor"
DB_PASSWORD = ""
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "music_charts"
S3_BUCKET = "music-charts-pipeline-orontavor"

engine = create_engine(f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")


def load_from_s3(snapshot_date=None):
    if snapshot_date is None:
        snapshot_date = date.today().isoformat()
    key = f"clean/{snapshot_date}/charts_clean.csv"
    print(f"Reading s3://{S3_BUCKET}/{key}")
    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
    df = pd.read_csv(io.BytesIO(obj["Body"].read()))
    _write_to_postgres(df, snapshot_date)


def _write_to_postgres(df, snapshot_date):
    # Guard: don't load the same day twice if the pipeline is run more than once.
    with engine.connect() as conn:
        try:
            result = conn.execute(
                text("SELECT COUNT(*) FROM raw_chart_entries WHERE snapshot_date = :d"),
                {"d": snapshot_date}
            )
            already_loaded = result.scalar() > 0
        except Exception:
            # Table doesn't exist yet — first ever load, safe to proceed.
            already_loaded = False

    if already_loaded:
        print(f"Snapshot {snapshot_date} already in Postgres — skipping load.")
        return

    # Append this day's rows — never replace, so history accumulates.
    df.to_sql("raw_chart_entries", engine, if_exists="append", index=False)
    print(f"Loaded {len(df)} rows for {snapshot_date} into raw_chart_entries")


def load(csv_path="charts_clean.csv"):
    df = pd.read_csv(csv_path)
    snapshot_date = df["snapshot_date"].iloc[0]
    _write_to_postgres(df, snapshot_date)


if __name__ == "__main__":
    import sys
    # No argument -> load today's date (used by the daily cron job).
    # One argument (YYYY-MM-DD) -> backfill that specific day.
    snapshot_date = sys.argv[1] if len(sys.argv) > 1 else None
    load_from_s3(snapshot_date)
