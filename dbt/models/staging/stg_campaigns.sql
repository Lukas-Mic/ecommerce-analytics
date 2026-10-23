with source as (
    select * from {{ source('raw', 'campaigns') }}
)

select
    campaign_id::int                                  as campaign_id,
    campaign_name,
    channel,
    campaign_type,
    start_date::date                                  as start_date,
    end_date::date                                    as end_date,
    daily_budget::numeric(10, 2)                      as daily_budget,
    discount_pct::numeric(5, 2)                       as discount_pct,
    nullif(trim(target_category), '')                 as target_category
from source
