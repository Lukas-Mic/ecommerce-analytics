-- Zwrot nie może przekroczyć wartości pozycji ani zwrócić więcej sztuk niż kupiono.
select order_item_id, net_amount, refund_amount, quantity, returned_quantity
from {{ ref('fct_order_items') }}
where refund_amount > net_amount + 0.01
   or returned_quantity > quantity
