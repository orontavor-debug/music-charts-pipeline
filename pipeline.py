import os
from datetime import date
import pandas as pd
from dotenv import load_dotenv
from src.lastfm import get_global_chart

load_dotenv()
API_KEY = os.getenv("LASTFM_API_KEY")
SNAPSHOT_DATE = date.today().isoformat()


def fetch_global(api_key):
    raw = get_global_chart(api_key)
    rows = []
    for rank, track in enumerate(raw, start=1):
        rows.append({
            "snapshot_date": SNAPSHOT_DATE,
            "chart_scope": "global",
            "rank": rank,
            "track_name": track["name"],
            "artist_name": track["artist"]["name"],
            "playcount": track["playcount"],
            "listeners": track["listeners"],
            "mbid": track.get("mbid", ""),
            "url": track["url"],
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    print("Fetching global chart...")
    df_global = fetch_global(API_KEY)
    print(f"Got {len(df_global)} global tracks")
    print(df_global.head())
