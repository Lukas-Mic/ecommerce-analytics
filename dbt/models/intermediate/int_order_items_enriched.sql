-- Pozycja zamówienia z wartościami: brutto, rabat, netto, koszt, zwroty.
-- (Kwoty "netto" = po rabacie; ceny w sklepie zawierają VAT.)
with items as (
    select * from {{ ref('stg_order_items') }}
),

products as (
    select product_id, unit_cost from {{ ref('stg_products') }}
),

returns as (
    select
        order_item_id,
        sum(returned_quantity)                        as returned_quantity,
        sum(refund_amount)                            as refund_amount,
        min(return_date)                              as first_return_date
    from {{ ref('stg_returns') }}
    group by 1
)

select
    i.order_item_id,
    i.order_id,
    i.product_id,
    i.quantity,
    i.unit_price,
    i.discount_pct,
    round(i.quantity * i.unit_price, 2)                                    as gross_amount,
    round(i.quantity * i.unit_price, 2)
        - round(i.quantity * i.unit_price * (1 - i.discount_pct), 2)       as discount_amount,
    round(i.quantity * i.unit_price * (1 - i.discount_pct), 2)             as net_amount,
    round(i.quantity * p.unit_cost, 2)                                     as cogs_amount,
    coalesce(r.returned_quantity, 0)                                       as returned_quantity,
    coalesce(r.refund_amount, 0)                                           as refund_amount,
    round(coalesce(r.returned_quantity, 0) * p.unit_cost, 2)               as returned_cogs_amount,
    r.first_return_date
from items i
join products p using (product_id)
left join returns r using (order_item_id)
