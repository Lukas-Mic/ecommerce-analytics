-- Wymiar: klient (tylko konta główne, bez kont testowych).
-- Dane osobowe ograniczone: zamiast e-maila i nazwiska udostępniamy hash e-maila.
with customers as (
    select * from {{ ref('stg_customers') }}
    where account_rank = 1
      and not is_test_account
),

order_stats as (
    select
        customer_id,
        min(order_date) filter (where not is_cancelled)            as first_order_date,
        max(order_date) filter (where not is_cancelled)            as last_order_date,
        count(*) filter (where not is_cancelled)                   as orders_count,
        sum(net_revenue_after_returns)                             as lifetime_revenue,
        sum(gross_margin)                                          as lifetime_margin
    from {{ ref('fct_orders') }}
    group by 1
),

bounds as (
    select min(order_date) as data_start, max(order_date) as data_end
    from {{ ref('fct_orders') }}
)

select
    c.customer_id,
    md5(c.email)                                                   as email_hash,
    c.first_name,
    c.gender,
    c.birth_year,
    case
        when extract(year from b.data_end) - c.birth_year < 25 then '18-24'
        when extract(year from b.data_end) - c.birth_year < 35 then '25-34'
        when extract(year from b.data_end) - c.birth_year < 45 then '35-44'
        when extract(year from b.data_end) - c.birth_year < 55 then '45-54'
        else '55+'
    end                                                            as age_band,
    c.city,
    c.voivodeship,
    c.signup_date,
    c.acquisition_channel,
    c.signup_date >= b.data_start                                  as is_new_in_period,
    s.first_order_date,
    s.last_order_date,
    date_trunc('month', s.first_order_date)::date                  as cohort_month,
    coalesce(s.orders_count, 0)                                    as orders_count,
    coalesce(s.lifetime_revenue, 0)                                as lifetime_revenue,
    coalesce(s.lifetime_margin, 0)                                 as lifetime_margin,
    case
        when s.last_order_date is null then 'bez zamówień'
        when b.data_end - s.last_order_date <= 180 then 'aktywny'
        when b.data_end - s.last_order_date <= 365 then 'uśpiony'
        else 'utracony'
    end                                                            as customer_status
from customers c
cross join bounds b
left join order_stats s using (customer_id)
