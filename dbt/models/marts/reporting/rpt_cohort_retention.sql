-- Retencja kohort: odsetek klientów z kohorty (miesiąc pierwszego zamówienia),
-- którzy kupili ponownie w kolejnych miesiącach.
-- Tylko klienci zarejestrowani w okresie danych: dla starszych klientów pierwsze
-- zamówienie w danych nie jest ich prawdziwym pierwszym zamówieniem.
with cohorts as (
    select customer_id, cohort_month
    from {{ ref('dim_customers') }}
    where is_new_in_period
      and cohort_month is not null
),

cohort_size as (
    select cohort_month, count(*) as cohort_customers
    from cohorts
    group by 1
),

activity as (
    select
        o.customer_id,
        date_trunc('month', o.order_date)::date                       as activity_month,
        sum(o.net_revenue_after_returns)                              as revenue
    from {{ ref('fct_orders') }} o
    where not o.is_cancelled
    group by 1, 2
),

joined as (
    select
        c.cohort_month,
        (extract(year from age(a.activity_month, c.cohort_month)) * 12
         + extract(month from age(a.activity_month, c.cohort_month)))::int as months_since_first_order,
        a.customer_id,
        a.revenue
    from cohorts c
    join activity a using (customer_id)
)

select
    j.cohort_month,
    j.months_since_first_order,
    s.cohort_customers,
    count(distinct j.customer_id)                                     as active_customers,
    round(count(distinct j.customer_id)::numeric / s.cohort_customers, 4) as retention_rate,
    sum(j.revenue)                                                    as revenue,
    round(sum(j.revenue) / s.cohort_customers, 2)                     as revenue_per_cohort_customer
from joined j
join cohort_size s using (cohort_month)
group by 1, 2, 3
order by 1, 2
