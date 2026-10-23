select
    product_id,
    sku,
    product_name,
    category,
    subcategory,
    brand,
    unit_cost,
    list_price,
    round((list_price - unit_cost) / nullif(list_price, 0), 4)    as list_margin_pct,
    case
        when list_price < 50 then '< 50 zł'
        when list_price < 150 then '50–149 zł'
        when list_price < 400 then '150–399 zł'
        else '400+ zł'
    end                                                            as price_band,
    launched_at
from {{ ref('stg_products') }}
