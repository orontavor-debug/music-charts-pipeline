import os
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("LASTFM_API_KEY")

BASE_URL = "https://ws.audioscrobbler.com/2.0/"

params = {
    "method": "chart.getTopTracks",
    "api_key": API_KEY,
    "format": "json",
    "limit": 50,
}

response = requests.get(BASE_URL, params=params)
data = response.json()

tracks = data["tracks"]["track"]

rows = []
for rank, track in enumerate(tracks, start=1):
    rows.append({
        "rank": rank,
        "track_name": track["name"],
        "artist_name": track["artist"]["name"],
        "playcount": track["playcount"],
        "listeners": track["listeners"],
        "mbid": track.get("mbid", ""),
        "url": track["url"],
    })

df = pd.DataFrame(rows)
df.to_csv("global_chart.csv", index=False)

print(f"Saved {len(df)} tracks to global_chart.csv")
print(df.head())
