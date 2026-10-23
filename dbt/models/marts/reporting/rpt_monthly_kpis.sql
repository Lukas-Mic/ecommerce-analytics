-- Miesięczne KPI zarządcze z dynamiką m/m i r/r.
-- Uwaga: zwroty przypisane są do miesiąca zamówienia, więc ostatni miesiąc
-- ma zaniżony wskaźnik zwrotów (zwroty jeszcze napływają).
with orders as (
    select
        date_trunc('month', order_date)::date                         as month_start,
        count(*) filter (where not is_cancelled)                      as orders,
        count(*) filter (where is_cancelled)                          as cancelled_orders,
        count(distinct customer_id) filter (where not is_cancelled)   as active_customers,
        count(*) filter (where is_first_order)                        as new_customers,
        sum(units) filter (where not is_cancelled)                    as units,
        sum(net_revenue)                                              as net_revenue,
        sum(case when is_cancelled then 0 else discount_amount end)   as discounts,
        sum(case when is_cancelled then 0 else refund_amount end)     as refunds,
        sum(net_revenue_after_returns)                                as net_revenue_after_returns,
        sum(gross_margin)                                             as gross_margin
    from {{ ref('fct_orders') }}
    group by 1
),

marketing as (
    select date_trunc('month', spend_date)::date as month_start, sum(spend) as marketing_spend
    from {{ ref('stg_marketing_spend') }}
    group by 1
),

combined as (
    select
        o.*,
        coalesce(m.marketing_spend, 0)                                as marketing_spend
    from orders o
    left join marketing m using (month_start)
)

select
    month_start,
    to_char(month_start, 'YYYY-MM')                                   as year_month,
    orders,
    cancelled_orders,
    active_customers,
    new_customers,
    active_customers - new_customers                                  as returning_customers,
    units,
    net_revenue,
    discounts,
    refunds,
    net_revenue_after_returns,
    gross_margin,
    marketing_spend,
    gross_margin - marketing_spend                                    as contribution_after_marketing,
    round(net_revenue / nullif(orders, 0), 2)                         as avg_order_value,
    round(gross_margin / nullif(net_revenue_after_returns, 0), 4)     as gross_margin_pct,
    round(refunds / nullif(net_revenue, 0), 4)                        as refund_rate,
    round(cancelled_orders::numeric / nullif(orders + cancelled_orders, 0), 4) as cancellation_rate,
    round(net_revenue / nullif(marketing_spend, 0), 2)                as marketing_efficiency_ratio,
    round(marketing_spend / nullif(new_customers, 0), 2)              as blended_cac,
    round(net_revenue / nullif(lag(net_revenue) over (order by month_start), 0) - 1, 4)     as revenue_mom,
    round(net_revenue / nullif(lag(net_revenue, 12) over (order by month_start), 0) - 1, 4) as revenue_yoy
from combined
order by month_start
