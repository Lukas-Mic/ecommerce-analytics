-- Fakt: pozycja zamówienia (ziarno: produkt w zamówieniu).
select
    i.order_item_id,
    i.order_id,
    o.customer_id,
    o.order_date,
    o.sales_channel,
    o.campaign_id,
    o.is_cancelled,
    i.product_id,
    i.quantity,
    i.unit_price,
    i.discount_pct,
    i.gross_amount,
    i.discount_amount,
    i.net_amount,
    i.cogs_amount,
    i.returned_quantity,
    i.refund_amount,
    i.returned_cogs_amount,
    case when o.is_cancelled then 0
         else (i.net_amount - i.refund_amount) - (i.cogs_amount - i.returned_cogs_amount)
    end                                               as gross_margin
from {{ ref('int_order_items_enriched') }} i
join {{ ref('fct_orders') }} o using (order_id)
