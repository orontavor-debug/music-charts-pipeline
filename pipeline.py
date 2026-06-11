import os
from datetime import date
import pandas as pd
from dotenv import load_dotenv
from src.lastfm import get_global_chart, get_country_chart, get_track_tags, pick_genre

COUNTRIES = ["united states", "united kingdom", "germany", "brazil", "japan"]

load_dotenv()
API_KEY = os.getenv("LASTFM_API_KEY")
# Every row gets today's date so we can track trends across daily snapshots.
SNAPSHOT_DATE = date.today().isoformat()


def fetch_global(api_key):
    raw = get_global_chart(api_key)
    rows = []
    # The global endpoint does NOT return a rank number, so we derive it from
    # list position — Last.fm returns tracks in popularity order (most popular first).
    for rank, track in enumerate(raw, start=1):
        rows.append({
            "snapshot_date": SNAPSHOT_DATE,
            "chart_scope": "global",
            "rank": rank,
            "track_name": track["name"],
            "artist_name": track["artist"]["name"],
            "playcount": track["playcount"],
            "listeners": track["listeners"],
            "mbid": track.get("mbid", ""),  # mbid is sometimes missing — .get() avoids a crash
            "url": track["url"],
        })
    return pd.DataFrame(rows)


def fetch_country(api_key, country):
    raw = get_country_chart(api_key, country)
    rows = []
    for track in raw:
        rows.append({
            "snapshot_date": SNAPSHOT_DATE,
            "chart_scope": country,
            # Country endpoint DOES return rank, but 0-based — add 1 to match global (1-based).
            "rank": int(track["@attr"]["rank"]) + 1,
            "track_name": track["name"],
            "artist_name": track["artist"]["name"],
            # geo endpoint doesn't always return playcount — use .get() to default to None.
            "playcount": track.get("playcount", None),
            # geo endpoint never returns listeners — None becomes NULL in Postgres. Expected.
            "listeners": None,
            "mbid": track.get("mbid", ""),
            "url": track["url"],
        })
    return pd.DataFrame(rows)


def quality_check(df):
    print("\n=== QUALITY CHECK ===")
    dupes = df.duplicated(subset=["snapshot_date", "chart_scope", "track_name", "artist_name"]).sum()
    print(f"Duplicate rows: {dupes} (expected 0)")
    print(f"Rows per chart:\n{df['chart_scope'].value_counts().to_string()}")
    print(f"Null track_name: {df['track_name'].isnull().sum()} (expected 0)")
    print(f"Null artist_name: {df['artist_name'].isnull().sum()} (expected 0)")
    print(f"Ranks out of range: {((df['rank'] < 1) | (df['rank'] > 50)).sum()} (expected 0)")
    print(f"Unknown genre: {(df['genre'] == 'unknown').sum()} / {len(df)} rows")
    print("=== END CHECK ===\n")


def enrich_with_genre(api_key, df):
    # Deduplicate first — many tracks appear on multiple charts.
    # Fetching genre once per unique track instead of once per row saves ~200 API calls.
    unique_tracks = df[["track_name", "artist_name"]].drop_duplicates()
    genre_map = {}
    print(f"Fetching genres for {len(unique_tracks)} unique tracks...", end="", flush=True)
    for _, row in unique_tracks.iterrows():
        key = (row["track_name"], row["artist_name"])
        tags = get_track_tags(api_key, row["track_name"], row["artist_name"])
        genre_map[key] = pick_genre(tags)
        print(".", end="", flush=True)
    print(" done")
    # Map the genre back onto all 300 rows using the lookup dictionary.
    df["genre"] = df.apply(lambda r: genre_map[(r["track_name"], r["artist_name"])], axis=1)
    return df


if __name__ == "__main__":
    print("Fetching global chart...")
    df_global = fetch_global(API_KEY)
    print(f"Got {len(df_global)} global tracks")

    all_frames = [df_global]
    for country in COUNTRIES:
        print(f"Fetching {country} chart...")
        df_country = fetch_country(API_KEY, country)
        print(f"  Got {len(df_country)} tracks")
        all_frames.append(df_country)

    # Stack all 6 DataFrames (1 global + 5 countries) into one table vertically.
    df_all = pd.concat(all_frames, ignore_index=True)
    print(f"\nCombined: {len(df_all)} rows across {df_all['chart_scope'].nunique()} charts")

    df_all = enrich_with_genre(API_KEY, df_all)

    print(f"\nGenre breakdown:")
    print(df_all["genre"].value_counts())
    print(f"\nRows with unknown genre: {(df_all['genre'] == 'unknown').sum()}")

    df_all.to_csv("charts_clean.csv", index=False)
    print(f"\nSaved {len(df_all)} rows to charts_clean.csv")

    quality_check(df_all)
