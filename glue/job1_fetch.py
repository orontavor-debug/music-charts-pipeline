import sys
import io
from datetime import date
import boto3
import pandas as pd
from awsglue.utils import getResolvedOptions

# Glue passes job parameters via sys.argv — getResolvedOptions extracts them.
# LASTFM_API_KEY and S3_BUCKET are set when the job is created in the console.
args = getResolvedOptions(sys.argv, ['LASTFM_API_KEY', 'S3_BUCKET'])
API_KEY = args['LASTFM_API_KEY']
S3_BUCKET = args['S3_BUCKET']
SNAPSHOT_DATE = date.today().isoformat()

COUNTRIES = ["united states", "united kingdom", "germany", "brazil", "japan"]

# --- inline API functions (same logic as src/lastfm.py) ---
import time
import requests

BASE_URL = "https://ws.audioscrobbler.com/2.0/"


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


def get_global_chart(api_key, limit=50):
    data = _call({"method": "chart.getTopTracks", "api_key": api_key, "format": "json", "limit": limit})
    return data["tracks"]["track"]


def get_country_chart(api_key, country, limit=50):
    data = _call({"method": "geo.getTopTracks", "api_key": api_key, "country": country, "format": "json", "limit": limit})
    return data["tracks"]["track"]


# --- fetch ---
rows = []

print("Fetching global chart...")
for rank, track in enumerate(get_global_chart(API_KEY), start=1):
    rows.append({
        "snapshot_date": SNAPSHOT_DATE,
        "chart_scope": "global",
        "rank": rank,
        "track_name": track["name"],
        "artist_name": track["artist"]["name"],
        "playcount": track["playcount"],
        "listeners": track["listeners"],
        "mbid": track.get("mbid", ""),
        "artist_mbid": track["artist"].get("mbid", ""),
        "url": track["url"],
    })

for country in COUNTRIES:
    print(f"Fetching {country} chart...")
    for track in get_country_chart(API_KEY, country):
        rows.append({
            "snapshot_date": SNAPSHOT_DATE,
            "chart_scope": country,
            "rank": int(track["@attr"]["rank"]) + 1,
            "track_name": track["name"],
            "artist_name": track["artist"]["name"],
            "playcount": track.get("playcount", None),
            "listeners": None,
            "mbid": track.get("mbid", ""),
            "artist_mbid": track["artist"].get("mbid", ""),
            "url": track["url"],
        })

df = pd.DataFrame(rows)
print(f"Total rows fetched: {len(df)}")

# --- save to S3 ---
# Write CSV to an in-memory buffer, then upload to S3.
# Glue runs in the cloud so there's no local filesystem to write to.
s3_client = boto3.client('s3')
buffer = io.StringIO()
df.to_csv(buffer, index=False)
key = f"raw/{SNAPSHOT_DATE}/charts_raw.csv"
s3_client.put_object(Bucket=S3_BUCKET, Key=key, Body=buffer.getvalue())
print(f"Saved to s3://{S3_BUCKET}/{key}")
