with distinct_artists as (
    select distinct
        artist_name,
        artist_mbid,
        artist_origin_country,
        artist_type,
        artist_gender,
        artist_begin_year
    from {{ ref('stg_chart_entries') }}
)

select
    md5(artist_name || '-' || coalesce(artist_mbid, '')) as artist_key,
    artist_name,
    artist_mbid,
    artist_origin_country,
    artist_type,
    artist_gender,
    artist_begin_year
from distinct_artists
