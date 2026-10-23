with source as (
    select * from {{ source('raw', 'marketing_spend') }}
)

select
    date::date                                        as spend_date,
    campaign_id::int                                  as campaign_id,
    channel,
    spend::numeric(12, 2)                             as spend,
    impressions::int                                  as impressions,
    clicks::int                                       as clicks
from source
