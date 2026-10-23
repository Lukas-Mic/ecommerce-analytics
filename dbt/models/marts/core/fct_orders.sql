-- Fakt: jedno zamówienie = jeden wiersz.
-- Klient przypisany do konta głównego (scalone duplikaty), konta testowe wykluczone.
with orders as (
    select * from {{ ref('stg_orders') }}
),

customers as (
    select customer_id, master_customer_id, is_test_account
    from {{ ref('stg_customers') }}
),

items as (
    select
        order_id,
        count(*)                                      as line_count,
        sum(quantity)                                 as units,
        sum(gross_amount)                             as gross_amount,
        sum(discount_amount)                          as discount_amount,
        sum(net_amount)                               as net_amount,
        sum(cogs_amount)                              as cogs_amount,
        sum(refund_amount)                            as refund_amount,
        sum(returned_cogs_amount)                     as returned_cogs_amount
    from {{ ref('int_order_items_enriched') }}
    group by 1
),

joined as (
    select
        o.order_id,
        c.master_customer_id                          as customer_id,
        o.order_date,
        o.order_ts_local,
        o.order_ts_utc,
        o.order_status,
        o.order_status = 'cancelled'                  as is_cancelled,
        o.sales_channel,
        o.device,
        o.campaign_id,
        o.payment_method,
        o.shipping_method,
        o.shipping_cost,
        coalesce(i.line_count, 0)                     as line_count,
        coalesce(i.units, 0)                          as units,
        coalesce(i.gross_amount, 0)                   as gross_amount,
        coalesce(i.discount_amount, 0)                as discount_amount,
        coalesce(i.net_amount, 0)                     as net_amount,
        coalesce(i.cogs_amount, 0)                    as cogs_amount,
        coalesce(i.refund_amount, 0)                  as refund_amount,
        coalesce(i.returned_cogs_amount, 0)           as returned_cogs_amount
    from orders o
    join customers c using (customer_id)
    left join items i using (order_id)
    where not c.is_test_account
),

metrics as (
    select
        *,
        case when is_cancelled then 0 else net_amount end                    as net_revenue,
        case when is_cancelled then 0 else net_amount - refund_amount end    as net_revenue_after_returns,
        case when is_cancelled then 0
             else (net_amount - refund_amount) - (cogs_amount - returned_cogs_amount)
        end                                                                  as gross_margin,
        case when is_cancelled then null
             else row_number() over (
                 partition by customer_id, is_cancelled order by order_ts_utc, order_id)
        end                                                                  as customer_order_seq
    from joined
)

select
    *,
    coalesce(customer_order_seq = 1, false)           as is_first_order
from metrics
