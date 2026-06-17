with distinct_genres as (
    select distinct genre
    from {{ ref('stg_chart_entries') }}
)

select
    md5(genre) as genre_key,
    genre
from distinct_genres
