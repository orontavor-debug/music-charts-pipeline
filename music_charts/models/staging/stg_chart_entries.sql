with source as (
    select * from {{ source('music_charts', 'raw_chart_entries') }}
),

renamed as (
    select
        snapshot_date::date                         as snapshot_date,
        chart_scope,
        rank::integer                               as rank,
        track_name,
        artist_name,
        coalesce(nullif(genre, ''), 'unknown')      as genre,
        nullif(mbid, '')                            as track_mbid,
        nullif(artist_mbid, '')                     as artist_mbid,
        nullif(artist_origin_country, '')           as artist_origin_country,
        nullif(artist_type, '')                     as artist_type,
        nullif(artist_gender, '')                   as artist_gender,
        artist_begin_year::integer                  as artist_begin_year,
        playcount::bigint                           as playcount,
        listeners::bigint                           as listeners,
        url
    from source
)

select * from renamed
