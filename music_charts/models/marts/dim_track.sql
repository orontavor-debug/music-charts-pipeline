with distinct_tracks as (
    select
        track_name,
        artist_name,
        max(track_mbid) as track_mbid,
        max(url) as url
    from {{ ref('stg_chart_entries') }}
    group by track_name, artist_name
)

select
    md5(track_name || '-' || artist_name) as track_key,
    track_name,
    artist_name,
    track_mbid,
    url
from distinct_tracks
