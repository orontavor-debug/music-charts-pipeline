with fact_with_date as (
    select
        f.*,
        d.snapshot_date
    from {{ ref('fact_chart_entry') }} f
    left join {{ ref('dim_date') }} d on f.date_key = d.date_key
),

with_previous_rank as (
    select
        *,
        lag(rank) over (
            partition by track_key, country_key
            order by snapshot_date
        ) as previous_rank
    from fact_with_date
)

select
    date_key,
    country_key,
    artist_key,
    track_key,
    genre_key,
    snapshot_date,
    rank,
    previous_rank,
    previous_rank - rank as rank_change,
    playcount,
    listeners
from with_previous_rank
