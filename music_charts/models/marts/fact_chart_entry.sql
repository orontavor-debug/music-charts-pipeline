select
    md5(snapshot_date::text) as date_key,
    md5(chart_scope) as country_key,
    md5(artist_name || '-' || coalesce(artist_mbid, '')) as artist_key,
    md5(track_name || '-' || artist_name) as track_key,
    md5(genre) as genre_key,
    rank,
    playcount,
    listeners
from {{ ref('stg_chart_entries') }}
