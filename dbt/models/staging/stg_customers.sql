-- Typowanie i czyszczenie kont klientów oraz rozpoznanie duplikatów po e-mailu.
-- Każde konto dostaje master_customer_id = najwcześniej założone konto z tym samym e-mailem.
with source as (
    select * from {{ source('raw', 'customers') }}
),

cleaned as (
    select
        customer_id::int                              as customer_id,
        initcap(trim(first_name))                     as first_name,
        initcap(trim(last_name))                      as last_name,
        lower(trim(email))                            as email,
        nullif(initcap(trim(city)), '')               as city,
        lower(trim(voivodeship))                      as voivodeship,
        signup_date::date                             as signup_date,
        acquisition_channel,
        birth_year::int                               as birth_year,
        gender,
        lower(trim(email)) like '%@test.%'            as is_test_account
    from source
)

select
    *,
    first_value(customer_id) over w                   as master_customer_id,
    row_number() over w                               as account_rank
from cleaned
window w as (partition by email order by signup_date, customer_id)
