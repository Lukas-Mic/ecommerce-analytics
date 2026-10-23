-- Zamówienia: usunięcie zdublowanych wierszy z ETL i konwersja czasu UTC -> Europe/Warsaw.
with source as (
    select * from {{ source('raw', 'orders') }}
),

typed as (
    select
        order_id::bigint                              as order_id,
        customer_id::int                              as customer_id,
        order_ts::timestamptz                         as order_ts_utc,
        (order_ts::timestamptz at time zone 'Europe/Warsaw') as order_ts_local,
        status                                        as order_status,
        channel                                       as sales_channel,
        device,
        nullif(campaign_id, '')::int                  as campaign_id,
        payment_method,
        shipping_method,
        shipping_cost::numeric(10, 2)                 as shipping_cost,
        _loaded_at
    from source
),

deduplicated as (
    select
        *,
        row_number() over (partition by order_id order by _loaded_at) as row_num
    from typed
)

select
    order_id,
    customer_id,
    order_ts_utc,
    order_ts_local,
    order_ts_local::date                              as order_date,
    order_status,
    sales_channel,
    device,
    campaign_id,
    payment_method,
    shipping_method,
    shipping_cost
from deduplicated
where row_num = 1
