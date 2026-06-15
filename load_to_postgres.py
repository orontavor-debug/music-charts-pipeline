import pandas as pd
from sqlalchemy import create_engine, text

DB_USER = "orontavor"
DB_PASSWORD = ""
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "music_charts"

engine = create_engine(f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")


def load(csv_path="charts_clean.csv"):
    df = pd.read_csv(csv_path)
    snapshot_date = df["snapshot_date"].iloc[0]

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


if __name__ == "__main__":
    load()
