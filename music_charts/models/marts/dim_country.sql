with distinct_charts as (
    select distinct chart_scope
    from {{ ref('stg_chart_entries') }}
)

select
    md5(chart_scope) as country_key,
    chart_scope
from distinct_charts
