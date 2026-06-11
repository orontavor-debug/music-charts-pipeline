import time
import requests

BASE_URL = "https://ws.audioscrobbler.com/2.0/"
PAUSE_SECONDS = 0.25

KNOWN_GENRES = {
    "pop", "rock", "hip-hop", "r&b", "rnb", "soul", "jazz", "classical",
    "electronic", "dance", "indie", "alternative", "metal", "punk",
    "country", "folk", "reggae", "latin", "k-pop", "j-pop", "schlager",
    "bossa nova", "funk", "blues", "trap", "rap",
    "pop rock", "indie pop", "indie rock", "dance-pop", "electropop",
    "pop punk", "synthpop", "art pop", "dream pop",
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
    time.sleep(PAUSE_SECONDS)


def get_global_chart(api_key, limit=50):
    params = {
        "method": "chart.getTopTracks",
        "api_key": api_key,
        "format": "json",
        "limit": limit,
    }
    data = _call(params)
    return data["tracks"]["track"]


def get_country_chart(api_key, country, limit=50):
    params = {
        "method": "geo.getTopTracks",
        "api_key": api_key,
        "country": country,
        "format": "json",
        "limit": limit,
    }
    data = _call(params)
    return data["tracks"]["track"]


def get_track_tags(api_key, track_name, artist_name):
    params = {
        "method": "track.getTopTags",
        "api_key": api_key,
        "track": track_name,
        "artist": artist_name,
        "format": "json",
    }
    data = _call(params)
    tags = data.get("toptags", {}).get("tag", [])
    return [t["name"].lower().strip() for t in tags]


def pick_genre(tags):
    for tag in tags:
        if tag in KNOWN_GENRES:
            return tag
    return "unknown"