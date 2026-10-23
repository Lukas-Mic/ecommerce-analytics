-- Rekoncyliacja: suma wartości netto zamówień musi być równa sumie pozycji.
select o.total_orders, i.total_items
from (select sum(net_amount) as total_orders from {{ ref('fct_orders') }}) o
cross join (select sum(net_amount) as total_items from {{ ref('fct_order_items') }}) i
where abs(o.total_orders - i.total_items) > 0.01
