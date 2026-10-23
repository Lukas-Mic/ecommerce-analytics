with source as (
    select * from {{ source('raw', 'returns') }}
)

select
    return_id::int                                    as return_id,
    order_item_id::bigint                             as order_item_id,
    return_date::date                                 as return_date,
    returned_quantity::int                            as returned_quantity,
    reason                                            as return_reason,
    refund_amount::numeric(10, 2)                     as refund_amount
from source
