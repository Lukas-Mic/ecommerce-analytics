-- Pozycje zamówień: naprawa przecinka dziesiętnego i odrzucenie pozycji z ilością <= 0.
with source as (
    select * from {{ source('raw', 'order_items') }}
)

select
    order_item_id::bigint                             as order_item_id,
    order_id::bigint                                  as order_id,
    product_id::int                                   as product_id,
    quantity::int                                     as quantity,
    replace(unit_price, ',', '.')::numeric(10, 2)     as unit_price,
    discount_pct::numeric(5, 2)                       as discount_pct
from source
where quantity::int > 0
