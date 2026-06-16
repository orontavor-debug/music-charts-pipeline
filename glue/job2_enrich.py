import sys
import io
import time
import requests
from datetime import date
import boto3
import pandas as pd
from awsglue.utils import getResolvedOptions

args = getResolvedOptions(sys.argv, ['LASTFM_API_KEY', 'S3_BUCKET'])
API_KEY = args['LASTFM_API_KEY']
S3_BUCKET = args['S3_BUCKET']
SNAPSHOT_DATE = date.today().isoformat()

s3_client = boto3.client('s3')

# --- read raw file from S3 ---
raw_key = f"raw/{SNAPSHOT_DATE}/charts_raw.csv"
print(f"Reading s3://{S3_BUCKET}/{raw_key}")
obj = s3_client.get_object(Bucket=S3_BUCKET, Key=raw_key)
df = pd.read_csv(io.BytesIO(obj['Body'].read()))
print(f"Loaded {len(df)} rows")

# --- Last.fm genre functions ---
BASE_URL = "https://ws.audioscrobbler.com/2.0/"

KNOWN_GENRES = {
    "pop", "rock", "hip-hop", "r&b", "rnb", "soul", "jazz", "classical",
    "electronic", "dance", "indie", "alternative", "metal", "punk",
    "country", "folk", "reggae", "latin", "k-pop", "j-pop", "schlager",
    "bossa nova", "funk", "blues", "trap", "rap",
    "pop rock", "indie pop", "indie rock", "dance-pop", "electropop",
    "pop punk", "synthpop", "art pop", "dream pop",
    "pop rap", "alt-pop", "dark pop", "alternative pop",
}


def _call(params, retries=3):
    for attempt in range(retries):
        try:
            response = requests.get(BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                raise ValueError(f"Last.fm error {data['error']}: {data['message']}")
            return data
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise e
    time.sleep(0.25)


def get_track_tags(api_key, track_name, artist_name):
    data = _call({"method": "track.getTopTags", "api_key": api_key, "track": track_name, "artist": artist_name, "format": "json"})
    tags = data.get("toptags", {}).get("tag", [])
    return [t["name"].lower().strip() for t in tags]


def pick_genre(tags):
    for tag in tags:
        if tag in KNOWN_GENRES:
            return tag
    return "unknown"


# --- MusicBrainz functions ---
MB_URL = "https://musicbrainz.org/ws/2/"
MB_HEADERS = {"User-Agent": "music-charts-pipeline/0.1 (orontavor@gmail.com)"}


def get_artist(mbid, retries=3):
    url = f"{MB_URL}artist/{mbid}?fmt=json"
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=MB_HEADERS, timeout=10)
            response.raise_for_status()
            data = response.json()
            begin = data.get("life-span", {}).get("begin")
            return {
                "artist_origin_country": data.get("country", None),
                "artist_type": data.get("type", None),
                "artist_gender": data.get("gender", None),
                "artist_begin_year": begin.split("-")[0] if begin else None,
            }
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                return _empty_result()
    time.sleep(1.1)


def _empty_result():
    return {"artist_origin_country": None, "artist_type": None, "artist_gender": None, "artist_begin_year": None}


# --- enrich genre ---
unique_tracks = df[["track_name", "artist_name"]].drop_duplicates()
genre_map = {}
print(f"Fetching genres for {len(unique_tracks)} unique tracks...")
for _, row in unique_tracks.iterrows():
    key = (row["track_name"], row["artist_name"])
    tags = get_track_tags(API_KEY, row["track_name"], row["artist_name"])
    genre_map[key] = pick_genre(tags)
    time.sleep(0.25)
df["genre"] = df.apply(lambda r: genre_map[(r["track_name"], r["artist_name"])], axis=1)
print("Genre enrichment done")

# --- enrich MusicBrainz ---
unique_artists = df[["artist_name", "artist_mbid"]].drop_duplicates(subset=["artist_mbid"])
artist_map = {}
print(f"Fetching MusicBrainz metadata for {len(unique_artists)} unique artists...")
for _, row in unique_artists.iterrows():
    mbid = str(row["artist_mbid"]).strip()
    artist_map[mbid] = get_artist(mbid) if mbid and mbid != "nan" else _empty_result()
    time.sleep(1.1)
for col in ["artist_origin_country", "artist_type", "artist_gender", "artist_begin_year"]:
    df[col] = df["artist_mbid"].apply(lambda m: artist_map.get(str(m).strip(), _empty_result())[col])
print("MusicBrainz enrichment done")

# --- quality check ---
dupes = df.duplicated(subset=["snapshot_date", "chart_scope", "track_name", "artist_name"]).sum()
print(f"Duplicate rows: {dupes} (expected 0)")
print(f"Rows per chart:\n{df['chart_scope'].value_counts().to_string()}")
print(f"Unknown genre: {(df['genre'] == 'unknown').sum()} / {len(df)} rows")

# --- save clean file to S3 ---
buffer = io.StringIO()
df.to_csv(buffer, index=False)
clean_key = f"clean/{SNAPSHOT_DATE}/charts_clean.csv"
s3_client.put_object(Bucket=S3_BUCKET, Key=clean_key, Body=buffer.getvalue())
print(f"Saved to s3://{S3_BUCKET}/{clean_key}")
