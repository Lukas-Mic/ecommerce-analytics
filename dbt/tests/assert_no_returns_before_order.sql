-- Zwrot nie może być zarejestrowany przed datą zamówienia.
select return_id, order_date, return_date
from {{ ref('fct_returns') }}
where days_to_return < 0
