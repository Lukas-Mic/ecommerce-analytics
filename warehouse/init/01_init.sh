#!/bin/bash
# Uruchamiany automatycznie przy pierwszym starcie kontenera Postgres (pusty wolumen).
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
     -v bi_pw="$BI_READER_PASSWORD" -v mb_pw="$METABASE_DB_PASSWORD" <<'EOSQL'
-- Warstwy hurtowni
CREATE SCHEMA IF NOT EXISTS raw;           -- dane źródłowe 1:1 (wszystko jako tekst)
CREATE SCHEMA IF NOT EXISTS staging;       -- czyszczenie i typowanie (dbt, widoki)
CREATE SCHEMA IF NOT EXISTS intermediate;  -- logika pośrednia (dbt, widoki)
CREATE SCHEMA IF NOT EXISTS marts;         -- model gwiazdy i raporty (dbt, tabele)

REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- Rola tylko do odczytu dla narzędzi BI: widzi wyłącznie schemat marts
CREATE ROLE bi_reader LOGIN PASSWORD :'bi_pw';
GRANT USAGE ON SCHEMA marts TO bi_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA marts TO bi_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA marts GRANT SELECT ON TABLES TO bi_reader;
ALTER ROLE bi_reader SET default_transaction_read_only = on;
ALTER ROLE bi_reader SET statement_timeout = '60s';

-- Osobna baza na metadane Metabase
CREATE ROLE metabase LOGIN PASSWORD :'mb_pw';
CREATE DATABASE metabase OWNER metabase;
REVOKE CONNECT ON DATABASE metabase FROM PUBLIC;
EOSQL

echo "Inicjalizacja hurtowni zakończona."
