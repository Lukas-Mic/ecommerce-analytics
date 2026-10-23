-- Raport jakości danych: co znaleziono w źródłach i co z tym zrobiła hurtownia.
-- Nadaje się wprost na stronę "Data quality" w dashboardzie.
with checks as (

    select 'customers' as source_table,
           'Duplikaty kont (ten sam e-mail, inna wielkość liter / spacje)' as check_name,
           count(*) filter (where account_rank > 1) as issue_count,
           count(*) as row_count,
           'Scalone do konta głównego (master_customer_id)' as resolution
    from {{ ref('stg_customers') }}

    union all
    select 'customers', 'Konta testowe zespołu QA',
           count(*) filter (where is_test_account), count(*),
           'Wykluczone razem z zamówieniami z warstwy marts'
    from {{ ref('stg_customers') }}

    union all
    select 'customers', 'Niestandardowy zapis miasta (wielkość liter, spacje, puste)',
           count(*) filter (where city is null or trim(city) = '' or city <> initcap(trim(city))), count(*),
           'Ujednolicone (initcap, trim, puste -> NULL)'
    from {{ source('raw', 'customers') }}

    union all
    select 'customers', 'Niestandardowy zapis województwa',
           count(*) filter (where voivodeship <> lower(trim(voivodeship))), count(*),
           'Ujednolicone (lower, trim)'
    from {{ source('raw', 'customers') }}

    union all
    select 'orders', 'Zdublowane wiersze zamówień (błąd ETL)',
           count(*) - count(distinct order_id), count(*),
           'Usunięte w stg_orders (row_number po order_id)'
    from {{ source('raw', 'orders') }}

    union all
    select 'order_items', 'Cena z przecinkiem dziesiętnym',
           count(*) filter (where unit_price like '%,%'), count(*),
           'Zamienione na kropkę i rzutowane na numeric'
    from {{ source('raw', 'order_items') }}

    union all
    select 'order_items', 'Pozycje z ilością <= 0',
           count(*) filter (where quantity::int <= 0), count(*),
           'Odrzucone w stg_order_items'
    from {{ source('raw', 'order_items') }}

    union all
    select 'returns', 'Zwroty powiązane z odrzuconymi pozycjami zamówień',
           count(*) filter (where i.order_item_id is null), count(*),
           'Pominięte w fct_returns; do weryfikacji w systemie magazynowym'
    from {{ ref('stg_returns') }} r
    left join {{ ref('stg_order_items') }} i using (order_item_id)

    union all
    select 'products', 'Kategoria z nadmiarowymi spacjami',
           count(*) filter (where category <> trim(category)), count(*),
           'Ujednolicone (trim)'
    from {{ source('raw', 'products') }}

    union all
    select 'marketing_spend', 'Dni kampanii płatnych z przychodem, ale bez danych o kosztach',
           count(*) filter (where is_spend_missing and orders > 0), count(*),
           'Pozostawione jako NULL i oznaczone flagą is_spend_missing; do wyjaśnienia z zespołem marketingu'
    from {{ ref('fct_marketing_daily') }}
)

select
    source_table,
    check_name,
    issue_count,
    row_count,
    round(issue_count::numeric / nullif(row_count, 0), 4)            as issue_rate,
    case when issue_count = 0 then 'OK' else 'Wykryto' end            as status,
    resolution
from checks
