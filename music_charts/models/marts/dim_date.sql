with distinct_dates as (
    select distinct snapshot_date
    from {{ ref('stg_chart_entries') }}
)

select
    md5(snapshot_date::text) as date_key,
    snapshot_date,
    extract(year from snapshot_date)::integer as year,
    extract(month from snapshot_date)::integer as month,
    extract(day from snapshot_date)::integer as day,
    to_char(snapshot_date, 'Day') as day_of_week
from distinct_dates
