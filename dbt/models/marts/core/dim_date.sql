-- Kalendarz z polskimi nazwami i świętami (seed pl_holidays).
with bounds as (
    select
        date_trunc('year', min(order_date))::date                     as d0,
        (date_trunc('year', max(order_date)) + interval '1 year - 1 day')::date as d1
    from {{ ref('stg_orders') }}
),

days as (
    select generate_series(d0, d1, interval '1 day')::date as date_day
    from bounds
)

select
    d.date_day,
    extract(year from d.date_day)::int                                as year,
    extract(quarter from d.date_day)::int                             as quarter,
    extract(month from d.date_day)::int                               as month,
    to_char(d.date_day, 'YYYY-MM')                                    as year_month,
    date_trunc('month', d.date_day)::date                             as month_start,
    (array['styczeń', 'luty', 'marzec', 'kwiecień', 'maj', 'czerwiec', 'lipiec',
           'sierpień', 'wrzesień', 'październik', 'listopad', 'grudzień']
    )[extract(month from d.date_day)::int]                            as month_name,
    extract(isoyear from d.date_day)::int                             as iso_year,
    extract(week from d.date_day)::int                                as iso_week,
    extract(isodow from d.date_day)::int                              as day_of_week,
    (array['poniedziałek', 'wtorek', 'środa', 'czwartek', 'piątek', 'sobota', 'niedziela']
    )[extract(isodow from d.date_day)::int]                           as day_name,
    extract(isodow from d.date_day) in (6, 7)                         as is_weekend,
    h.holiday_name,
    coalesce(h.is_day_off, false)                                     as is_holiday,
    extract(isodow from d.date_day) < 6 and not coalesce(h.is_day_off, false) as is_working_day
from days d
left join {{ ref('pl_holidays') }} h on h.holiday_date = d.date_day
