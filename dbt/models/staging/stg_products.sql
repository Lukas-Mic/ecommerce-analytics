with source as (
    select * from {{ source('raw', 'products') }}
)

select
    product_id::int                                   as product_id,
    sku,
    regexp_replace(trim(product_name), '\s+', ' ', 'g') as product_name,
    trim(category)                                    as category,
    trim(subcategory)                                 as subcategory,
    brand,
    unit_cost::numeric(10, 2)                         as unit_cost,
    list_price::numeric(10, 2)                        as list_price,
    launched_at::date                                 as launched_at
from source
