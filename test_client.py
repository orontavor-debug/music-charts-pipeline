import os
from dotenv import load_dotenv
from src.lastfm import get_global_chart, get_country_chart, get_track_tags, pick_genre

load_dotenv()
API_KEY = os.getenv("LASTFM_API_KEY")

print("--- Global chart (first 2 tracks) ---")
global_tracks = get_global_chart(API_KEY, limit=2)
for t in global_tracks:
    print(f"  {t['name']} by {t['artist']['name']}")

print("\n--- Japan chart (first 2 tracks) ---")
japan_tracks = get_country_chart(API_KEY, "japan", limit=2)
for t in japan_tracks:
    print(f"  {t['name']} by {t['artist']['name']}")

print("\n--- Tags + genre for first 10 global tracks ---")
global_10 = get_global_chart(API_KEY, limit=10)
for track in global_10:
    tags = get_track_tags(API_KEY, track["name"], track["artist"]["name"])
    genre = pick_genre(tags)
    print(f"  {track['name']} by {track['artist']['name']}")
    print(f"    Tags: {tags[:5]}")
    print(f"    Genre: {genre}")
