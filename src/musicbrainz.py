import time
import requests

BASE_URL = "https://musicbrainz.org/ws/2/"

# MusicBrainz requires a descriptive User-Agent header — requests without it are rejected.
HEADERS = {"User-Agent": "music-charts-pipeline/0.1 (orontavor@gmail.com)"}

# Strict rate limit: MusicBrainz allows ~1 request/second. Going faster risks a block.
PAUSE_SECONDS = 1.1


def get_artist(mbid, retries=3):
    url = f"{BASE_URL}artist/{mbid}?fmt=json"
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            data = response.json()
            return {
                "artist_origin_country": data.get("country", None),
                "artist_type": data.get("type", None),
                # Gender is only meaningful for solo artists — groups return None.
                "artist_gender": data.get("gender", None),
                # begin date can be full (1989-12-13) or year-only (2001) — we take just the year.
                "artist_begin_year": _parse_year(data.get("life-span", {}).get("begin")),
            }
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                return _empty_result()
    time.sleep(PAUSE_SECONDS)


def _parse_year(begin):
    if not begin:
        return None
    # begin can be "1989-12-13" or just "2001" — split on "-" and take the first part.
    return begin.split("-")[0]


def _empty_result():
    # Returned when an artist has no MBID or the lookup fails — keeps the pipeline running.
    return {
        "artist_origin_country": None,
        "artist_type": None,
        "artist_gender": None,
        "artist_begin_year": None,
    }
