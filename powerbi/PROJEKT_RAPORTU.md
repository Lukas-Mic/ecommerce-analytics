# Raport Power BI: projekt stron

Format strony: 16:9 (domyślny). Motyw: `motyw-ecommerce.json`
(Widok → Motywy → Przeglądaj w poszukiwaniu motywów).

Każda strona ma ten sam układ:

```
┌──────────────────────────────────────────────────────────────┐
│ Tytuł strony                [Zakres dat]  [Kanał]  [Kategoria]│  ← fragmentatory
├──────────┬──────────┬──────────┬──────────┬──────────────────┤
│  Karta   │  Karta   │  Karta   │  Karta   │  Karta           │  ← KPI
├──────────┴──────────┴──────────┼──────────┴──────────────────┤
│                                │                             │
│      wykres główny             │      wykres pomocniczy      │
│                                │                             │
├────────────────────────────────┼─────────────────────────────┤
│      wykres / tabela           │  Pole tekstowe: Wnioski     │
└────────────────────────────────┴─────────────────────────────┘
```

**Fragmentatory** (te same na każdej stronie, zsynchronizuj je: Widok → Synchronizuj fragmentatory):
- `dim_date[date_day]` - styl **Między** (suwak dat)
- `fct_orders[sales_channel]` - lista rozwijana
- `dim_products[category]` - lista rozwijana (na stronach 1 i 3)

**Zasady wizualne:**
- Jedna oś Y na wykresie. Dwie miary o różnej skali to dwa wykresy, nigdy wykres z dwiema osiami.
- Kolory kanałów/kategorii stałe na wszystkich stronach (motyw nadaje je w kolejności).
- Na wykresach z kolorami 3-5 (zielonkawy, żółty, różowy) włącz etykiety danych - te kolory
  mają słabszy kontrast z tłem.
- Etykiety danych selektywnie (np. tylko na słupkach), nie na każdym punkcie linii.

---

## Model: nagłówek i pozycje zamówienia

`fct_order_items` łączy się z `fct_orders` (wiele-do-jednego, `order_id`), a nie bezpośrednio
z `dim_date`, `dim_customers` i `dim_campaigns`. Filtry daty, klienta, kampanii i kanału płyną
wymiar → `fct_orders` → `fct_order_items`, a filtr produktu/kategorii trafia wprost do pozycji.
Miary sprzedażowe liczą z pozycji, więc reagują na wszystkie fragmentatory.

---

## Strona 1: Przegląd zarządczy

**Karty KPI** (Karta, wartość + w opcjach „Etykieta kategorii”):
`Przychód netto` · `Marża brutto %` · `Zamówienia` · `Średnia wartość zamówienia` · `Dynamika r/r (porównywalne okresy)`

| Wizualizacja | Pola | Uwagi |
|---|---|---|
| Wykres liniowy: Przychód miesięcznie | Oś X: `dim_date[month_start]` · Y: `Przychód netto`, `Przychód netto rok wcześniej` | Dwie linie na tej samej osi = porównanie r/r. Oś X jako typ ciągły. |
| Wykres słupkowy poziomy: Kategorie | Oś Y: `dim_products[category]` · X: `Przychód netto` | Sortuj malejąco. |
| Macierz: Kategoria x miesiąc | Wiersze: `dim_products[category]` · Kolumny: `dim_date[year]` · Wartości: `Marża brutto %` | Formatowanie warunkowe: skala kolorów tła (niebieska). |

> **Przychód wg kategorii:** miary sprzedażowe liczą z `fct_order_items` (ziarno: pozycja), bo
> może mieć produkty z kilku). Do wykresu kategorii dodaj miarę:
> nagłówek zamówienia nie ma kategorii - jedno zamówienie może mieć produkty z kilku.
> Dzięki temu filtr kategorii działa na wszystkich kartach. Temat na rozmowę: **ziarno tabeli faktów**.

**Wnioski do znalezienia:** sezonowość (listopad-grudzień), wzrost r/r ok. 30-40%,
marża rośnie w 2026.

---

## Strona 2: Klienci

**Karty KPI:** `Aktywni klienci` · `Nowi klienci` · `Udział powracających` · `Przychód na klienta` · `Zamówienia na klienta`

| Wizualizacja | Pola | Uwagi |
|---|---|---|
| Wykres kolumnowy skumulowany: Nowi vs powracający | Oś X: `dim_date[month_start]` · Y: `Nowi klienci`, `Powracający klienci` | |
| Macierz: Kohorty retencji | Wiersze: `rpt_cohort_retention[cohort_month]` · Kolumny: `months_since_first_order` · Wartości: `retention_rate` (Suma) | Formatowanie warunkowe tła: niebieska skala. Klasyczna „trójkątna” tabela kohort. |
| Wykres słupkowy: Segmenty RFM | Oś Y: `rpt_customer_rfm[rfm_segment]` · X: Liczba `customer_id` | Kliknięcie segmentu filtruje resztę strony. |
| Mapa kształtów lub słupki: Województwa | `dim_customers[voivodeship]` · `Przychód po zwrotach` | Mapa wymaga pliku TopoJSON województw; słupki są prostsze. |

**Uwaga:** macierz kohort nie reaguje na fragmentator dat (tabela bez relacji) - to celowe, dodaj podpis.

**Wnioski do znalezienia:** retencja po 1. miesiącu, który segment RFM daje najwięcej przychodu.

---

## Strona 3: Marketing

**Karty KPI:** `Koszt marketingu` · `ROAS` · `MER` · `CAC` · `Marża po marketingu`

| Wizualizacja | Pola | Uwagi |
|---|---|---|
| Wykres kolumnowy: ROAS wg kanału | Oś X: `dim_campaigns[channel_name]` · Y: `ROAS` | Linia referencyjna (Analityka → Linia stała) na 1,0. |
| Tabela: Kampanie | `dim_campaigns[campaign_name]`, `Koszt marketingu`, `Przychód z kampanii`, `ROAS`, `CAC`, `CTR` | Paski danych na `ROAS`; sortowanie po koszcie. |
| Wykres liniowy: Koszt marketingu w czasie | Oś X: `dim_date[month_start]` · Y: `Koszt marketingu` · Legenda: `dim_campaigns[channel_name]` | |
| Wykres punktowy: Koszt vs przychód kampanii | X: `Koszt marketingu` · Y: `Przychód z kampanii` · Szczegóły: `campaign_name` · Legenda: `channel_name` | Maks. 3 kanały w legendzie albo filtr na płatne media. |

**Wnioski do znalezienia:** newsletter ma najwyższy ROAS przy niskim koszcie, Black Week
podnosi koszt, ale też CAC.

---

## Strona 4: Jakość danych i anomalie

Ta strona wyróżnia projekt - pokazuje, że dane źródłowe są sprawdzane, a nie przyjmowane na wiarę.

**Karty KPI:** `Anomalia zamówień` (liczba dni - użyj COUNTROWS w osobnej miarze lub pokaż na wykresie) ·
`Dni bez danych kosztowych` · Suma `dq_data_quality_checks[issue_count]`

| Wizualizacja | Pola | Uwagi |
|---|---|---|
| Wykres liniowy dzienny: Zamówienia i anomalie | Oś X: `dim_date[date_day]` · Y: `Zamówienia` (linia), `Anomalia zamówień` (jako znaczniki, linia wyłączona) | Fragmentator dat ustaw na 2026-02 do 2026-04 i pokaż **awarię płatności 10-12.03.2026**. Dodaj adnotację (pole tekstowe). |
| Tabela: Raport jakości danych | `dq_data_quality_checks`: `source_table`, `check_name`, `issue_count`, `issue_rate`, `resolution` | Formatowanie warunkowe ikon na `issue_rate`. |
| Wykres kolumnowy: Koszt Meta w lipcu 2025 | Oś X: `dim_date[date_day]` · Y: `Koszt marketingu` · filtr: `channel = meta_ads`, lipiec 2025 | Widoczna luka 1-5.07 = **luka w eksporcie danych**, nie brak kampanii. |

**Wnioski do znalezienia:** jak hurtownia wykrywa i obsługuje problemy, dwa incydenty.

---

## Pole „Wnioski” na każdej stronie

Napisz 2-3 zdania **własnymi słowami**: co widać i co z tego wynika dla biznesu.
To jest część, której AI nie powinno pisać za Ciebie - rekruter chce zobaczyć,
jak myślisz o danych. Mogę je potem przejrzeć.
