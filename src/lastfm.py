import time
import requests

BASE_URL = "https://ws.audioscrobbler.com/2.0/"

# Polite pause between API calls to avoid hitting Last.fm's rate limit (error 29).
PAUSE_SECONDS = 0.25

# Last.fm tags are crowd-sourced and messy — usernames, personal labels, etc. appear
# alongside real genres. We filter against this allowlist and take the first match.
# "unknown" is the intentional fallback when no real genre tag is found.
KNOWN_GENRES = {
    "pop", "rock", "hip-hop", "r&b", "rnb", "soul", "jazz", "classical",
    "electronic", "dance", "indie", "alternative", "metal", "punk",
    "country", "folk", "reggae", "latin", "k-pop", "j-pop", "schlager",
    "bossa nova", "funk", "blues", "trap", "rap",
    "pop rock", "indie pop", "indie rock", "dance-pop", "electropop",
    "pop punk", "synthpop", "art pop", "dream pop",
}


def _call(params, retries=3):
    # Leading underscore means "internal use only" — callers use the public functions below.
    for attempt in range(retries):
        try:
            response = requests.get(BASE_URL, params=params, timeout=10)
            response.raise_for_status()  # raises if HTTP status is 4xx or 5xx
            data = response.json()
            # Last.fm returns error details inside the JSON even on HTTP 200,
            # so we check for them explicitly.
            if "error" in data:
                raise ValueError(f"Last.fm error {data['error']}: {data['message']}")
            return data
        except Exception as e:
            if attempt < retries - 1:
                # Exponential backoff: wait 1s, then 2s, then give up.
                # Gives the API time to recover before retrying.
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
    # country must be a full ISO country name in lowercase, e.g. "united states", "germany".
    # This endpoint covers "most popular last week" — slightly different time window than global.
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
    # Tags are returned sorted by popularity (most-used first) — order matters for pick_genre().
    tags = data.get("toptags", {}).get("tag", [])
    return [t["name"].lower().strip() for t in tags]


def pick_genre(tags):
    # Tags come in popularity order, so the first match is the most-used real genre tag.
    for tag in tags:
        if tag in KNOWN_GENRES:
            return tag
    return "unknown"
