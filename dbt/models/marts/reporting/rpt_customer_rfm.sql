-- Segmentacja RFM (Recency, Frequency, Monetary) na dzień ostatnich danych.
with reference as (
    select max(order_date) + 1 as ref_date from {{ ref('fct_orders') }}
),

base as (
    select
        o.customer_id,
        r.ref_date - max(o.order_date)                                as recency_days,
        count(*)                                                      as frequency,
        sum(o.net_revenue_after_returns)                              as monetary
    from {{ ref('fct_orders') }} o
    cross join reference r
    where not o.is_cancelled
    group by o.customer_id, r.ref_date
),

scored as (
    select
        *,
        ntile(5) over (order by recency_days desc)                    as r_score,
        ntile(5) over (order by frequency, monetary)                  as f_score,
        ntile(5) over (order by monetary)                             as m_score
    from base
)

select
    customer_id,
    recency_days,
    frequency,
    monetary,
    r_score,
    f_score,
    m_score,
    concat(r_score, f_score, m_score)                                 as rfm_code,
    case
        when r_score >= 4 and f_score >= 4 then 'Mistrzowie'
        when r_score >= 3 and f_score >= 3 then 'Lojalni'
        when r_score >= 4 then 'Nowi'
        when r_score = 3 then 'Obiecujący'
        when f_score >= 4 then 'Nie można stracić'
        when f_score = 3 then 'Zagrożeni odejściem'
        when r_score = 2 then 'Uśpieni'
        else 'Utraceni'
    end                                                               as rfm_segment
from scored
