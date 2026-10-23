-- Ładowanie plików CSV do schematu raw (landing zone).
-- Wszystkie kolumny jako text: surowe dane trafiają do hurtowni bez zmian,
-- a typowanie i czyszczenie robi warstwa staging w dbt.
-- Uruchomienie: make load

\set ON_ERROR_STOP on
BEGIN;

DROP TABLE IF EXISTS raw.customers, raw.products, raw.campaigns, raw.orders,
                     raw.order_items, raw.returns, raw.marketing_spend;

CREATE TABLE raw.customers (
    customer_id text, first_name text, last_name text, email text, city text,
    voivodeship text, signup_date text, acquisition_channel text, birth_year text, gender text,
    _loaded_at timestamptz DEFAULT now()
);
CREATE TABLE raw.products (
    product_id text, sku text, product_name text, category text, subcategory text, brand text,
    unit_cost text, list_price text, launched_at text,
    _loaded_at timestamptz DEFAULT now()
);
CREATE TABLE raw.campaigns (
    campaign_id text, campaign_name text, channel text, campaign_type text, start_date text,
    end_date text, daily_budget text, discount_pct text, target_category text,
    _loaded_at timestamptz DEFAULT now()
);
CREATE TABLE raw.orders (
    order_id text, customer_id text, order_ts text, status text, channel text, device text,
    campaign_id text, payment_method text, shipping_method text, shipping_cost text,
    _loaded_at timestamptz DEFAULT now()
);
CREATE TABLE raw.order_items (
    order_item_id text, order_id text, product_id text, quantity text, unit_price text,
    discount_pct text,
    _loaded_at timestamptz DEFAULT now()
);
CREATE TABLE raw.returns (
    return_id text, order_item_id text, return_date text, returned_quantity text, reason text,
    refund_amount text,
    _loaded_at timestamptz DEFAULT now()
);
CREATE TABLE raw.marketing_spend (
    date text, campaign_id text, channel text, spend text, impressions text, clicks text,
    _loaded_at timestamptz DEFAULT now()
);

\copy raw.customers (customer_id, first_name, last_name, email, city, voivodeship, signup_date, acquisition_channel, birth_year, gender) FROM '/data/raw/customers.csv' WITH (FORMAT csv, HEADER true)
\copy raw.products (product_id, sku, product_name, category, subcategory, brand, unit_cost, list_price, launched_at) FROM '/data/raw/products.csv' WITH (FORMAT csv, HEADER true)
\copy raw.campaigns (campaign_id, campaign_name, channel, campaign_type, start_date, end_date, daily_budget, discount_pct, target_category) FROM '/data/raw/campaigns.csv' WITH (FORMAT csv, HEADER true)
\copy raw.orders (order_id, customer_id, order_ts, status, channel, device, campaign_id, payment_method, shipping_method, shipping_cost) FROM '/data/raw/orders.csv' WITH (FORMAT csv, HEADER true)
\copy raw.order_items (order_item_id, order_id, product_id, quantity, unit_price, discount_pct) FROM '/data/raw/order_items.csv' WITH (FORMAT csv, HEADER true)
\copy raw.returns (return_id, order_item_id, return_date, returned_quantity, reason, refund_amount) FROM '/data/raw/returns.csv' WITH (FORMAT csv, HEADER true)
\copy raw.marketing_spend (date, campaign_id, channel, spend, impressions, clicks) FROM '/data/raw/marketing_spend.csv' WITH (FORMAT csv, HEADER true)

COMMIT;

SELECT 'customers' AS tabela, count(*) AS wiersze FROM raw.customers
UNION ALL SELECT 'products', count(*) FROM raw.products
UNION ALL SELECT 'campaigns', count(*) FROM raw.campaigns
UNION ALL SELECT 'orders', count(*) FROM raw.orders
UNION ALL SELECT 'order_items', count(*) FROM raw.order_items
UNION ALL SELECT 'returns', count(*) FROM raw.returns
UNION ALL SELECT 'marketing_spend', count(*) FROM raw.marketing_spend;
