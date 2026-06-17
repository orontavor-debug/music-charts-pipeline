with distinct_tracks as (
    select distinct
        track_name,
        artist_name,
        track_mbid,
        url
    from {{ ref('stg_chart_entries') }}
)

select
    md5(track_name || '-' || artist_name) as track_key,
    track_name,
    artist_name,
    track_mbid,
    url
from distinct_tracks
