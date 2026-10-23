SHELL := /bin/bash
COMPOSE := docker compose
TOOLS := $(COMPOSE) run --rm tools
PSQL := $(COMPOSE) exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" "$$@"' --

.PHONY: help env up down generate load build test docs psql all reset status

help: ## Lista poleceń
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

env: ## Tworzy .env z szablonu (potem zmień hasła!)
	@test -f .env || (cp .env.example .env && echo "Utworzono .env - ustaw własne hasła.")

up: ## Uruchamia Postgres i Metabase
	$(COMPOSE) up -d postgres metabase

down: ## Zatrzymuje kontenery (dane zostają)
	$(COMPOSE) down

generate: ## Generuje syntetyczne dane CSV do data/raw
	$(TOOLS) python generator/generate_data.py --out data/raw

load: ## Ładuje CSV do schematu raw
	$(PSQL) -f /warehouse/load_raw.sql

build: ## dbt: seedy, modele i testy
	$(TOOLS) dbt build --project-dir dbt

test: ## dbt: same testy
	$(TOOLS) dbt test --project-dir dbt

docs: ## Dokumentacja dbt z grafem zależności na http://localhost:8080
	$(TOOLS) dbt docs generate --project-dir dbt
	$(COMPOSE) run --rm -p 127.0.0.1:8080:8080 tools dbt docs serve --project-dir dbt --host 0.0.0.0 --port 8080 --no-browser

psql: ## Konsola SQL hurtowni
	$(COMPOSE) exec postgres sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'

status: ## Rozmiar bazy i liczba wierszy w marts
	$(PSQL) -c "select pg_size_pretty(pg_database_size(current_database())) as rozmiar_bazy;" \
	        -c "select relname as tabela, n_live_tup as wiersze from pg_stat_user_tables where schemaname = 'marts' order by 1;"

all: env up generate load build ## Wszystko od zera: dane -> hurtownia -> modele

reset: ## UWAGA: usuwa kontenery razem z danymi
	@read -p "Usunąć wszystkie dane hurtowni i Metabase? [t/N] " a && [ "$$a" = "t" ]
	$(COMPOSE) down -v
