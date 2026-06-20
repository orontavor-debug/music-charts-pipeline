with distinct_artists as (
    select
        artist_name,
        artist_mbid,
        max(artist_origin_country) as artist_origin_country,
        max(artist_type) as artist_type,
        max(artist_gender) as artist_gender,
        max(artist_begin_year) as artist_begin_year
    from {{ ref('stg_chart_entries') }}
    group by artist_name, artist_mbid
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
