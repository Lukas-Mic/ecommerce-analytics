-- Dzień x kampania: koszty z panelu reklamowego vs przychód z atrybucji last-click.
-- FULL JOIN celowo pokazuje dni z przychodem, ale bez kosztów (luka w danych źródłowych).
with spend as (
    select
        spend_date                                    as date_day,
        campaign_id,
        sum(spend)                                    as spend,
        sum(impressions)                              as impressions,
        sum(clicks)                                   as clicks
    from {{ ref('stg_marketing_spend') }}
    group by 1, 2
),

attributed as (
    select
        order_date                                    as date_day,
        campaign_id,
        count(*) filter (where not is_cancelled)      as orders,
        count(*) filter (where is_first_order)        as new_customers,
        sum(net_revenue)                              as revenue,
        sum(gross_margin)                             as gross_margin
    from {{ ref('fct_orders') }}
    where campaign_id is not null
    group by 1, 2
),

joined as (
    select
        coalesce(s.date_day, a.date_day)              as date_day,
        coalesce(s.campaign_id, a.campaign_id)        as campaign_id,
        s.spend,
        s.impressions,
        s.clicks,
        coalesce(a.orders, 0)                         as orders,
        coalesce(a.new_customers, 0)                  as new_customers,
        coalesce(a.revenue, 0)                        as revenue,
        coalesce(a.gross_margin, 0)                   as gross_margin
    from spend s
    full join attributed a
        on s.date_day = a.date_day and s.campaign_id = a.campaign_id
)

select
    j.date_day,
    j.campaign_id,
    c.campaign_name,
    c.channel,
    c.channel_name,
    c.is_paid_media,
    c.campaign_type,
    j.spend,
    j.impressions,
    j.clicks,
    j.orders,
    j.new_customers,
    j.revenue,
    j.gross_margin,
    j.spend is null and c.is_paid_media               as is_spend_missing,
    round(j.clicks::numeric / nullif(j.impressions, 0), 4)   as ctr,
    round(j.spend / nullif(j.clicks, 0), 2)                  as cpc,
    round(j.revenue / nullif(j.spend, 0), 2)                 as roas,
    round(j.spend / nullif(j.orders, 0), 2)                  as cost_per_order
from joined j
join {{ ref('dim_campaigns') }} c using (campaign_id)
