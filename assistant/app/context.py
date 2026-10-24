"""Kontekst dla modelu: opis hurtowni budowany na żywo z bazy + reguły biznesowe."""
from __future__ import annotations

BUSINESS_RULES = """
Reguły biznesowe hurtowni (schemat marts, PostgreSQL 16):

- Dane: fikcyjny polski sklep internetowy, zamówienia od 2024-10-01 do 2026-09-30.
  Kwoty w PLN, brutto (z VAT), tak jak widzi je klient.
- fct_orders: 1 wiersz = 1 zamówienie. order_date = data w czasie Europe/Warsaw.
  net_revenue = przychód po rabatach (0 dla anulowanych), net_revenue_after_returns = po zwrotach,
  gross_margin = po zwrotach i koszcie towaru. Liczba zamówień = count(*) where not is_cancelled.
  is_first_order = pierwsze nieanulowane zamówienie klienta w danych.
- fct_order_items: 1 wiersz = pozycja (produkt w zamówieniu). Kategorie i produkty TYLKO tutaj
  (join dim_products po product_id). Przychód pozycji: sum(net_amount) where not is_cancelled.
  Nie sumuj net_revenue z fct_orders po joinie z pozycjami (zwielokrotnienie wierszy).
- fct_returns: zwroty; return_date, return_reason, refund_amount, days_to_return.
- fct_marketing_daily: dzień x kampania. spend = koszt, revenue = przychód z atrybucji last-click,
  roas = revenue/spend. Kanały: google_ads, meta_ads, tiktok_ads, newsletter, affiliate.
  is_spend_missing = brak danych kosztowych w eksporcie (luka w Meta 1-5.07.2025).
- dim_customers: klient (bez danych osobowych - brak nazwisk i e-maili). customer_status:
  aktywny / uśpiony / utracony / bez zamówień. is_new_in_period = rejestracja w okresie danych.
- dim_products, dim_campaigns, dim_date (polskie nazwy miesięcy i dni, święta: is_holiday).
- rpt_monthly_kpis: gotowe KPI miesięczne (przychód, AOV, marża %, CAC, MER, dynamika m/m i r/r).
- rpt_cohort_retention: retencja kohort miesięcznych. rpt_customer_rfm: segmenty RFM.
- dq_data_quality_checks: raport jakości danych źródłowych.
- Znane zdarzenia w danych: awaria płatności BLIK/kartą 10-12.03.2026, Black Week (koniec listopada),
  Singles Day 11.11, kategoria Moda ma ok. 17% zwrotów (głównie "Nie pasuje rozmiar").
"""

SYSTEM_PROMPT = """Jesteś analitykiem danych. Zamieniasz pytania po polsku na jedno zapytanie SQL
do hurtowni PostgreSQL 16 i proponujesz sposób pokazania wyniku.

Zasady SQL:
- Wyłącznie jedno zapytanie SELECT (może zaczynać się od WITH). Bez średników, bez DDL/DML.
- Używaj tylko tabel ze schematu marts i zawsze pisz je z prefiksem, np. marts.fct_orders.
- Aliasy kolumn po polsku w cudzysłowach, np. sum(net_revenue) as "Przychód netto".
- Kwoty zaokrąglaj do 2 miejsc, odsetki zwracaj jako ułamek zaokrąglony do 4 miejsc
  i oznacz w aliasie znakiem %, np. "Marża %".
- Szeregi czasowe sortuj rosnąco po dacie; rankingi malejąco. Maksymalnie 200 wierszy wyniku.
- Gdy pytanie jest niejednoznaczne, przyjmij rozsądną interpretację i opisz ją w "assumptions".

{rules}

Schemat (tabela: kolumna typ [wartości] -- opis):
{schema}

Odpowiedz WYŁĄCZNIE obiektem JSON, bez komentarza i bez bloków kodu:
{{"title": "krótki tytuł wyniku",
  "sql": "SELECT ...",
  "chart": {{"type": "line|bar|table|number", "x": "alias kolumny osi X lub null",
             "y": ["alias kolumny z wartościami", "..."]}},
  "assumptions": "przyjęte założenia, jedno zdanie"}}

Wykres: line dla szeregów czasowych, bar dla porównania kategorii (do ok. 20 pozycji),
number dla pojedynczej wartości, table dla pozostałych. W "y" podawaj tylko kolumny liczbowe
o tej samej jednostce (nie mieszaj złotówek z procentami na jednym wykresie).

Jeśli pytanie nie dotyczy danych sklepu albo nie da się na nie odpowiedzieć z tych tabel, zwróć
{{"title": null, "sql": null, "chart": null, "assumptions": null,
  "message": "uprzejme wyjaśnienie po polsku, o co można zapytać"}}.
"""

SUMMARY_PROMPT = """Jesteś analitykiem danych. Na podstawie wyniku zapytania napisz po polsku
2-4 zdania komentarza dla menedżera: najważniejsza liczba, trend lub różnica, ewentualnie
jedno pytanie do dalszej analizy. Używaj wyłącznie liczb z wyniku, nie zgaduj.
Odsetki (kolumny z % w nazwie) są ułamkami - 0.1234 to 12,3%. Format liczb polski
(spacja jako separator tysięcy, przecinek dziesiętny). Bez nagłówków i list."""


SCHEMA_SQL = """
select c.table_name, c.column_name, c.data_type,
       col_description(format('%I.%I', c.table_schema, c.table_name)::regclass, c.ordinal_position)
from information_schema.columns c
where c.table_schema = 'marts'
order by c.table_name, c.ordinal_position
"""

TABLE_DESC_SQL = """
select c.relname, obj_description(c.oid, 'pg_class')
from pg_class c join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'marts' and c.relkind in ('r', 'v', 'm')
"""

LOW_CARDINALITY_MAX = 25
SKIP_VALUE_COLUMNS = {"first_name", "email_hash", "product_name", "sku", "campaign_name",
                      "check_name", "resolution", "rfm_code", "city", "holiday_name"}


def build_schema(run_query) -> str:
    """Opis schematu marts z bazy: kolumny, typy, opisy z dbt i przykładowe wartości tekstowe."""
    _, cols = run_query(SCHEMA_SQL)
    _, tdesc = run_query(TABLE_DESC_SQL)
    table_desc = {t: d for t, d in tdesc if d}

    lines, current = [], None
    for table, column, dtype, descr in cols:
        if table != current:
            current = table
            header = f"\nmarts.{table}"
            if table in table_desc:
                header += f" -- {' '.join(table_desc[table].split())}"
            lines.append(header)
        entry = f"  {column} {dtype}"
        if dtype in ("text", "character varying") and column not in SKIP_VALUE_COLUMNS:
            _, vals = run_query(
                f'select distinct "{column}" from marts."{table}" where "{column}" is not null '
                f'order by 1 limit {LOW_CARDINALITY_MAX + 1}')
            if 0 < len(vals) <= LOW_CARDINALITY_MAX:
                entry += " [" + ", ".join(str(v[0]) for v in vals) + "]"
        if descr:
            entry += f" -- {' '.join(descr.split())}"
        lines.append(entry)
    return "\n".join(lines).strip()
