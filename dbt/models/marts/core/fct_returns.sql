-- Fakt: zwrot (ziarno: zgłoszenie zwrotu pozycji).
select
    r.return_id,
    r.order_item_id,
    i.order_id,
    i.customer_id,
    i.product_id,
    i.order_date,
    r.return_date,
    r.return_date - i.order_date                      as days_to_return,
    r.returned_quantity,
    r.return_reason,
    r.refund_amount
from {{ ref('stg_returns') }} r
join {{ ref('fct_order_items') }} i using (order_item_id)
