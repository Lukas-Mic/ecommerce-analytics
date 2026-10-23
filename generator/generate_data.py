#!/usr/bin/env python3
"""
Generator syntetycznych danych e-commerce (polski sklep internetowy "Sklep Nadwiślański").

Tworzy pliki CSV w katalogu wyjściowym (domyślnie data/raw):
  customers.csv, products.csv, campaigns.csv, orders.csv,
  order_items.csv, returns.csv, marketing_spend.csv

Cechy danych:
  * sezonowość (Black Week, Singles Day, święta, wyprzedaże), dni tygodnia, trend wzrostowy,
  * sezonowość kategorii (kurtki zimą, ogród wiosną, zabawki w grudniu),
  * kampanie marketingowe z budżetem, rabatami i atrybucją zamówień,
  * zwroty zależne od kategorii (moda zwraca się najczęściej),
  * dwa "incydenty" do wykrycia w analizie (awaria bramki płatniczej, luka w danych Meta),
  * celowo wstrzyknięte problemy z jakością danych (duplikaty, literówki, przecinki dziesiętne),
    które warstwa staging w dbt musi naprawić.

Wszystkie dane są fikcyjne. Domeny e-mail są zarezerwowane (example.*), marki są wymyślone.
Wymagania: Python 3.10+, numpy, pandas.
"""
from __future__ import annotations

import argparse
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Słowniki
# ---------------------------------------------------------------------------
CITIES = [
    ("Warszawa", "mazowieckie", 18.0), ("Kraków", "małopolskie", 8.0),
    ("Wrocław", "dolnośląskie", 6.5), ("Łódź", "łódzkie", 6.0),
    ("Poznań", "wielkopolskie", 5.5), ("Gdańsk", "pomorskie", 4.8),
    ("Szczecin", "zachodniopomorskie", 3.6), ("Lublin", "lubelskie", 3.4),
    ("Bydgoszcz", "kujawsko-pomorskie", 3.1), ("Katowice", "śląskie", 2.8),
    ("Białystok", "podlaskie", 2.6), ("Gdynia", "pomorskie", 2.2),
    ("Rzeszów", "podkarpackie", 2.0), ("Częstochowa", "śląskie", 1.9),
    ("Toruń", "kujawsko-pomorskie", 1.9), ("Radom", "mazowieckie", 1.8),
    ("Kielce", "świętokrzyskie", 1.8), ("Sosnowiec", "śląskie", 1.7),
    ("Gliwice", "śląskie", 1.6), ("Olsztyn", "warmińsko-mazurskie", 1.6),
    ("Bielsko-Biała", "śląskie", 1.5), ("Zabrze", "śląskie", 1.4),
    ("Zielona Góra", "lubuskie", 1.4), ("Opole", "opolskie", 1.4),
    ("Bytom", "śląskie", 1.2), ("Rybnik", "śląskie", 1.2),
    ("Gorzów Wielkopolski", "lubuskie", 1.2), ("Płock", "mazowieckie", 1.1),
    ("Elbląg", "warmińsko-mazurskie", 1.0), ("Tarnów", "małopolskie", 1.0),
    ("Wałbrzych", "dolnośląskie", 0.9), ("Koszalin", "zachodniopomorskie", 0.9),
    ("Kalisz", "wielkopolskie", 0.9), ("Legnica", "dolnośląskie", 0.9),
    ("Nowy Sącz", "małopolskie", 0.8), ("Siedlce", "mazowieckie", 0.8),
    ("Piła", "wielkopolskie", 0.7), ("Zamość", "lubelskie", 0.7),
    ("Suwałki", "podlaskie", 0.6), ("Przemyśl", "podkarpackie", 0.6),
    ("Ostrowiec Świętokrzyski", "świętokrzyskie", 0.6), ("Nysa", "opolskie", 0.4),
]

FEMALE_FIRST = ["Anna", "Maria", "Katarzyna", "Małgorzata", "Agnieszka", "Barbara", "Ewa",
                "Krystyna", "Magdalena", "Joanna", "Aleksandra", "Zofia", "Monika", "Natalia",
                "Julia", "Karolina", "Marta", "Paulina", "Justyna", "Weronika", "Hanna",
                "Zuzanna", "Dominika", "Martyna", "Patrycja"]
MALE_FIRST = ["Piotr", "Krzysztof", "Andrzej", "Tomasz", "Paweł", "Michał", "Marcin", "Jakub",
              "Adam", "Łukasz", "Mateusz", "Kamil", "Grzegorz", "Marek", "Wojciech", "Bartosz",
              "Dawid", "Szymon", "Filip", "Jan", "Kacper", "Maciej", "Rafał", "Sebastian", "Damian"]
LAST_NAMES = [("Nowak", "Nowak"), ("Kowalski", "Kowalska"), ("Wiśniewski", "Wiśniewska"),
              ("Wójcik", "Wójcik"), ("Kowalczyk", "Kowalczyk"), ("Kamiński", "Kamińska"),
              ("Lewandowski", "Lewandowska"), ("Zieliński", "Zielińska"),
              ("Szymański", "Szymańska"), ("Woźniak", "Woźniak"), ("Dąbrowski", "Dąbrowska"),
              ("Kozłowski", "Kozłowska"), ("Jankowski", "Jankowska"), ("Mazur", "Mazur"),
              ("Kwiatkowski", "Kwiatkowska"), ("Krawczyk", "Krawczyk"),
              ("Piotrowski", "Piotrowska"), ("Grabowski", "Grabowska"),
              ("Nowakowski", "Nowakowska"), ("Pawłowski", "Pawłowska"),
              ("Michalski", "Michalska"), ("Adamczyk", "Adamczyk"), ("Dudek", "Dudek"),
              ("Zając", "Zając"), ("Wieczorek", "Wieczorek"), ("Jabłoński", "Jabłońska"),
              ("Król", "Król"), ("Majewski", "Majewska"), ("Olszewski", "Olszewska"),
              ("Jaworski", "Jaworska")]
EMAIL_DOMAINS = ["poczta.example.pl", "mail.example.com", "skrzynka.example.pl",
                 "example.net", "inbox.example.org"]

# sezonowość miesięczna (indeksy 0..11 = sty..gru)
SEASON = {
    "flat":        [1.0] * 12,
    "winter":      [1.4, 1.1, 0.9, 0.8, 0.7, 0.6, 0.6, 0.7, 1.0, 1.4, 1.6, 1.5],
    "garden":      [0.5, 0.6, 1.2, 1.6, 1.7, 1.4, 1.1, 0.9, 0.8, 0.6, 0.5, 0.6],
    "summer":      [0.6, 0.7, 0.9, 1.1, 1.4, 1.6, 1.6, 1.3, 0.9, 0.7, 0.6, 0.6],
    "gift":        [0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.9, 1.0, 1.5, 2.4],
    "electronics": [0.9, 0.8, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 1.0, 1.0, 1.6, 1.8],
    "fitness":     [1.6, 1.3, 1.1, 1.0, 1.1, 1.0, 0.9, 0.9, 1.0, 0.9, 0.9, 0.8],
    "school":      [0.7, 0.7, 0.8, 0.8, 0.8, 0.9, 1.0, 1.8, 1.6, 0.9, 0.9, 1.0],
}

# kategoria -> (kod, marki, [(podkategoria, rzeczowniki, (cena_min, cena_max), sezon)],
#               (koszt_min, koszt_max) jako ułamek ceny, wskaźnik zwrotów, waga popularności)
CATALOG = {
    "Elektronika": ("ELE", ["Voltra", "Nexo", "Sonora", "Pixelon", "Arkon"], [
        ("Słuchawki", ["Słuchawki bezprzewodowe", "Słuchawki nauszne", "Słuchawki sportowe"], (79, 599), "electronics"),
        ("Smartwatche", ["Smartwatch", "Opaska fitness"], (149, 999), "electronics"),
        ("Akcesoria GSM", ["Ładowarka", "Powerbank", "Kabel USB-C", "Etui"], (19, 199), "flat"),
        ("Głośniki", ["Głośnik Bluetooth", "Soundbar"], (99, 899), "electronics"),
    ], (0.62, 0.78), 0.05, 1.3),
    "Dom i ogród": ("DOM", ["Domira", "Lumo", "Verdo", "Kasztel"], [
        ("Oświetlenie", ["Lampa stołowa", "Kinkiet", "Taśma LED", "Lampa ogrodowa"], (39, 449), "flat"),
        ("Tekstylia", ["Koc", "Pościel", "Zasłony", "Ręczniki"], (49, 349), "winter"),
        ("Kuchnia", ["Patelnia", "Zestaw garnków", "Nóż szefa kuchni", "Czajnik"], (39, 599), "gift"),
        ("Ogród", ["Wąż ogrodowy", "Sekator", "Donica", "Leżak"], (29, 499), "garden"),
    ], (0.48, 0.65), 0.04, 1.2),
    "Moda": ("MOD", ["Norda", "Urbanica", "Velora", "Halny"], [
        ("Bluzy", ["Bluza z kapturem", "Bluza rozpinana"], (99, 299), "winter"),
        ("Buty sportowe", ["Sneakersy", "Buty do biegania"], (179, 549), "flat"),
        ("Kurtki", ["Kurtka puchowa", "Parka", "Kurtka przejściowa"], (249, 899), "winter"),
        ("Akcesoria", ["Czapka", "Szalik", "Plecak miejski", "Rękawiczki"], (39, 249), "winter"),
    ], (0.35, 0.50), 0.19, 1.5),
    "Sport": ("SPO", ["Kinetix", "Trekko", "Aktivo"], [
        ("Fitness", ["Hantle", "Mata do ćwiczeń", "Gumy oporowe", "Kettlebell"], (29, 399), "fitness"),
        ("Rowery – akcesoria", ["Lampka rowerowa", "Kask rowerowy", "Licznik rowerowy"], (39, 349), "summer"),
        ("Turystyka", ["Namiot", "Śpiwór", "Plecak trekkingowy", "Kijki trekkingowe"], (59, 899), "summer"),
    ], (0.50, 0.66), 0.06, 0.9),
    "Uroda": ("URO", ["Belleva", "Aurelle", "Siela"], [
        ("Pielęgnacja twarzy", ["Krem nawilżający", "Serum", "Tonik"], (25, 189), "flat"),
        ("Perfumy", ["Woda perfumowana", "Woda toaletowa"], (89, 459), "gift"),
        ("Włosy", ["Szampon", "Odżywka", "Suszarka do włosów", "Prostownica"], (19, 399), "flat"),
    ], (0.40, 0.55), 0.03, 1.1),
    "Dziecko": ("DZI", ["Tuptuś", "Mali Odkrywcy", "Gryzak"], [
        ("Zabawki", ["Klocki konstrukcyjne", "Puzzle", "Gra planszowa", "Pluszak"], (29, 349), "gift"),
        ("Szkoła", ["Plecak szkolny", "Piórnik", "Zestaw kredek"], (15, 249), "school"),
    ], (0.45, 0.60), 0.05, 0.8),
    "Zoo": ("ZOO", ["Pazur", "Merdo"], [
        ("Psy", ["Legowisko dla psa", "Smycz", "Zabawka dla psa", "Karma sucha 10 kg"], (19, 299), "flat"),
        ("Koty", ["Drapak", "Kuweta", "Karma mokra 24 szt."], (19, 349), "flat"),
    ], (0.55, 0.72), 0.03, 0.7),
}

RETURN_REASONS = ["Nie pasuje rozmiar", "Niezgodny z opisem", "Uszkodzony w transporcie",
                  "Zmiana decyzji", "Opóźniona dostawa", "Wada produktu"]
RETURN_REASON_P_FASHION = [0.48, 0.14, 0.05, 0.25, 0.04, 0.04]
RETURN_REASON_P_OTHER = [0.02, 0.24, 0.20, 0.30, 0.06, 0.18]

DAY_SEASON = [0.85, 0.80, 0.90, 0.95, 1.00, 0.92, 0.88, 0.90, 0.98, 1.05, 1.30, 1.40]
WEEKDAY = [1.08, 1.05, 1.02, 1.00, 0.95, 0.85, 1.05]  # pon..niedz
HOUR_P = np.array([0.6, 0.3, 0.2, 0.1, 0.1, 0.2, 0.6, 1.4, 2.4, 3.2, 3.8, 4.0, 4.4, 4.6,
                   4.4, 4.3, 4.5, 4.9, 5.6, 6.6, 7.6, 7.8, 5.6, 2.6])
HOUR_P = HOUR_P / HOUR_P.sum()

PAYMENT = (["blik", "card", "przelewy24", "cash_on_delivery", "paypo", "google_apple_pay"],
           [0.40, 0.24, 0.15, 0.07, 0.08, 0.06])
SHIPPING = {  # metoda: (cena, udział)
    "inpost_paczkomat": (13.99, 0.55),
    "courier_dpd": (16.99, 0.17),
    "courier_inpost": (15.99, 0.13),
    "orlen_paczka": (10.99, 0.10),
    "store_pickup": (0.00, 0.05),
}
FREE_SHIPPING_THRESHOLD = 199.0


def ascii_slug(text: str) -> str:
    text = text.replace("ł", "l").replace("Ł", "L")
    norm = unicodedata.normalize("NFKD", text)
    return "".join(c for c in norm if not unicodedata.combining(c)).lower().replace(" ", "")


def price_99(x: np.ndarray) -> np.ndarray:
    """Zaokrągla do ceny psychologicznej .99"""
    return np.maximum(np.floor(x) + 0.99, 9.99)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------
class Generator:
    def __init__(self, seed: int, start: str, end: str, n_customers: int, base_orders: float):
        self.rng = np.random.default_rng(seed)
        self.start = pd.Timestamp(start)
        self.end = pd.Timestamp(end)
        self.days = pd.date_range(self.start, self.end, freq="D")
        self.n_customers = n_customers
        self.base_orders = base_orders

    # -- produkty --------------------------------------------------------
    def products(self) -> pd.DataFrame:
        rng = self.rng
        rows = []
        pid = 1
        for cat, (code, brands, subcats, (cmin, cmax), ret_rate, pop) in CATALOG.items():
            for sub, nouns, (pmin, pmax), season in subcats:
                n = int(rng.integers(8, 15))
                for _ in range(n):
                    noun = rng.choice(nouns)
                    brand = rng.choice(brands)
                    model = rng.choice(["", " Pro", " Lite", " Max", " Air", " Classic", " Plus", " Eco"])
                    variant = rng.choice(["", " czarny", " biały", " szary", " granatowy", " zielony"])
                    list_price = float(price_99(np.exp(rng.uniform(np.log(pmin), np.log(pmax)))))
                    cost = round(list_price * rng.uniform(cmin, cmax), 2)
                    launched = self.start - pd.Timedelta(days=int(rng.integers(30, 900)))
                    if rng.random() < 0.2:  # nowości w trakcie okresu
                        launched = self.start + pd.Timedelta(days=int(rng.integers(0, len(self.days) - 60)))
                    rows.append({
                        "product_id": pid,
                        "sku": f"SKU-{code}-{pid:05d}",
                        "product_name": f"{noun} {brand}{model}{variant}".strip(),
                        "category": cat,
                        "subcategory": sub,
                        "brand": brand,
                        "unit_cost": cost,
                        "list_price": list_price,
                        "launched_at": launched.date(),
                        "_season": season,
                        "_return_rate": ret_rate,
                        "_pop": pop * rng.pareto(1.6) + 0.05,
                    })
                    pid += 1
        return pd.DataFrame(rows)

    # -- kampanie --------------------------------------------------------
    def campaigns(self) -> pd.DataFrame:
        rows = []
        cid = 1

        def add(name, channel, ctype, start, end, budget, discount=0.0, target=None, lift=0.0):
            nonlocal cid
            s, e = max(pd.Timestamp(start), self.start), min(pd.Timestamp(end), self.end)
            if s > e:
                return
            rows.append({"campaign_id": cid, "campaign_name": name, "channel": channel,
                         "campaign_type": ctype, "start_date": s.date(), "end_date": e.date(),
                         "daily_budget": budget, "discount_pct": discount,
                         "target_category": target, "lift_factor": lift})
            cid += 1

        add("Google Search – Brand", "google_ads", "always_on", self.start, self.end, 350)
        add("Google Shopping – PLA", "google_ads", "always_on", self.start, self.end, 900)
        add("Meta – Remarketing", "meta_ads", "always_on", self.start, self.end, 450)
        add("Afiliacja – sieć partnerska", "affiliate", "always_on", self.start, self.end, 0)
        add("TikTok – Always On", "tiktok_ads", "always_on", "2025-03-01", self.end, 250)

        for y in range(self.start.year, self.end.year + 1):
            add(f"Wyprzedaż zimowa {y}", "meta_ads", "promo", f"{y}-01-02", f"{y}-01-31", 700, 0.20, "Moda", 0.12)
            add(f"Wiosenne porządki {y}", "google_ads", "promo", f"{y}-03-15", f"{y}-04-15", 600, 0.15, "Dom i ogród", 0.08)
            add(f"Majówka {y}", "meta_ads", "promo", f"{y}-04-25", f"{y}-05-05", 800, 0.10, "Sport", 0.10)
            add(f"Lato w plenerze {y}", "tiktok_ads", "promo", f"{y}-06-10", f"{y}-07-15", 500, 0.10, "Sport", 0.07)
            add(f"Back to school {y}", "meta_ads", "promo", f"{y}-08-12", f"{y}-09-08", 550, 0.12, "Dziecko", 0.08)
            add(f"Singles Day {y}", "meta_ads", "promo", f"{y}-11-09", f"{y}-11-12", 1500, 0.11, None, 0.15)
            add(f"Black Week {y} – Google", "google_ads", "promo", f"{y}-11-21", f"{y}-12-02", 2200, 0.20, None, 0.10)
            add(f"Black Week {y} – Meta", "meta_ads", "promo", f"{y}-11-21", f"{y}-12-02", 1800, 0.20, None, 0.10)
            add(f"Prezenty świąteczne {y}", "meta_ads", "promo", f"{y}-12-03", f"{y}-12-20", 1200, 0.0, None, 0.08)
            for m in range(1, 13):
                d = pd.Timestamp(year=y, month=m, day=1)
                d = d + pd.Timedelta(days=(3 - d.weekday()) % 7)  # pierwszy czwartek miesiąca
                add(f"Newsletter {d:%Y-%m}", "newsletter", "newsletter", d, d, 150, 0.10, None, 0.35)
        return pd.DataFrame(rows)

    # -- dzienny wolumen zamówień ----------------------------------------
    def daily_volume(self, campaigns: pd.DataFrame) -> np.ndarray:
        rng = self.rng
        d = self.days
        t_years = (d - self.start).days / 365.25
        vol = self.base_orders * (1 + 0.32 * np.asarray(t_years, dtype=float))
        vol = vol * np.array([DAY_SEASON[m - 1] for m in d.month])
        vol = vol * np.array([WEEKDAY[w] for w in d.day_of_week])

        mult = np.ones(len(d))
        for y in range(self.start.year, self.end.year + 1):
            nov30 = pd.Timestamp(year=y, month=11, day=30)
            black_friday = nov30 - pd.Timedelta(days=(nov30.weekday() - 4) % 7)
            special = {
                black_friday: 3.1, black_friday + pd.Timedelta(days=1): 1.9,
                black_friday + pd.Timedelta(days=2): 1.6, black_friday + pd.Timedelta(days=3): 2.2,
                pd.Timestamp(year=y, month=11, day=11): 1.7,
                pd.Timestamp(year=y, month=12, day=24): 0.35, pd.Timestamp(year=y, month=12, day=25): 0.45,
                pd.Timestamp(year=y, month=12, day=26): 0.6, pd.Timestamp(year=y, month=12, day=31): 0.55,
                pd.Timestamp(year=y, month=1, day=1): 0.5,
            }
            for k in range(1, 5):
                special.setdefault(black_friday - pd.Timedelta(days=k), 1.35)
            for day, f in special.items():
                mult[d == day] *= f
            # ostatnie dni przed świętami - spadek po terminie gwarantowanej dostawy
            mult[(d >= pd.Timestamp(year=y, month=12, day=21)) & (d <= pd.Timestamp(year=y, month=12, day=23))] *= 0.7

        # incydent: awaria bramki płatności kartą i BLIK (do wykrycia w analizie anomalii)
        outage = (d >= pd.Timestamp("2026-03-10")) & (d <= pd.Timestamp("2026-03-12"))
        mult[outage] *= 0.38

        lift = np.ones(len(d))
        for c in campaigns.itertuples():
            active = (d >= pd.Timestamp(c.start_date)) & (d <= pd.Timestamp(c.end_date))
            lift[active] *= 1 + c.lift_factor
        noise = rng.lognormal(0, 0.09, len(d))
        return np.asarray(vol * mult * lift * noise, dtype=float)

    # -- klienci ---------------------------------------------------------
    def customers(self, day_weights: np.ndarray) -> pd.DataFrame:
        rng = self.rng
        n = self.n_customers
        n_pre = int(n * 0.25)
        pre_start = self.start - pd.Timedelta(days=640)
        pre_days = rng.integers(0, (self.start - pre_start).days, n_pre)
        signup_pre = pre_start + pd.to_timedelta(pre_days, unit="D")
        p = day_weights / day_weights.sum()
        signup_new = self.days[rng.choice(len(self.days), n - n_pre, p=p)]
        signup = pd.DatetimeIndex(np.concatenate([signup_pre.values, signup_new.values])).sort_values()

        gender = rng.choice(["F", "M"], n, p=[0.58, 0.42])
        first = np.where(gender == "F", rng.choice(FEMALE_FIRST, n), rng.choice(MALE_FIRST, n))
        ln_idx = rng.integers(0, len(LAST_NAMES), n)
        last = np.array([LAST_NAMES[i][0] if g == "M" else LAST_NAMES[i][1] for i, g in zip(ln_idx, gender)])
        cw = np.array([c[2] for c in CITIES])
        city_idx = rng.choice(len(CITIES), n, p=cw / cw.sum())
        acq = rng.choice(["organic", "google_ads", "meta_ads", "newsletter", "affiliate", "tiktok_ads"], n,
                         p=[0.34, 0.27, 0.18, 0.06, 0.08, 0.07])
        # TikTok wystartował w marcu 2025
        acq = np.where((acq == "tiktok_ads") & (signup < pd.Timestamp("2025-03-01")), "meta_ads", acq)
        birth_year = np.clip(np.round(rng.normal(1987, 11, n)), 1945, 2007).astype(int)

        emails = [f"{ascii_slug(f)}.{ascii_slug(l)}{rng.integers(1, 999)}@{rng.choice(EMAIL_DOMAINS)}"
                  for f, l in zip(first, last)]
        df = pd.DataFrame({
            "customer_id": np.arange(1, n + 1),
            "first_name": first, "last_name": last, "email": emails,
            "city": [CITIES[i][0] for i in city_idx],
            "voivodeship": [CITIES[i][1] for i in city_idx],
            "signup_date": signup.date,
            "acquisition_channel": acq,
            "birth_year": birth_year,
            "gender": gender,
        })
        # cechy behawioralne (niewidoczne w danych)
        df["_propensity"] = np.clip(rng.lognormal(0, 0.9, n), 0.05, 5.0)
        df["_churn_after_days"] = rng.exponential(420, n)
        df["_converts"] = rng.random(n) < 0.86
        return df

    # -- zamówienia ------------------------------------------------------
    def orders(self, customers: pd.DataFrame, volume: np.ndarray, campaigns: pd.DataFrame) -> pd.DataFrame:
        rng = self.rng
        signup = pd.to_datetime(customers["signup_date"]).values
        churn = signup + (customers["_churn_after_days"].values * 86400e9).astype("timedelta64[ns]")
        prop = customers["_propensity"].values
        ids = customers["customer_id"].values
        first_order_day = {}
        new_mask = (customers["_converts"].values) & (signup >= np.datetime64(self.start))
        for cid, s in zip(ids[new_mask], signup[new_mask]):
            first_order_day.setdefault(np.datetime64(s, "D"), []).append(cid)

        order_customer, order_day = [], []
        for i, day in enumerate(self.days.values):
            day_d = np.datetime64(day, "D")
            firsts = first_order_day.get(day_d, [])
            n_total = rng.poisson(volume[i])
            n_repeat = max(n_total - len(firsts), int(n_total * 0.25))
            eligible = (signup < day) & (churn > day)
            if eligible.any() and n_repeat > 0:
                w = prop[eligible]
                chosen = rng.choice(ids[eligible], n_repeat, p=w / w.sum())
                order_customer.extend(chosen.tolist())
                order_day.extend([day] * n_repeat)
            order_customer.extend(firsts)
            order_day.extend([day] * len(firsts))

        n = len(order_customer)
        days = pd.DatetimeIndex(order_day)
        hours = rng.choice(24, n, p=HOUR_P)
        local_ts = days + pd.to_timedelta(hours, unit="h") + pd.to_timedelta(rng.integers(0, 3600, n), unit="s")
        utc_ts = (local_ts.tz_localize("Europe/Warsaw", ambiguous=np.ones(n, dtype=bool),
                                       nonexistent="shift_forward").tz_convert("UTC"))

        t_years = (days - self.start).days.values / 365.25
        app_share = 0.24 + 0.08 * t_years
        u = rng.random(n)
        channel = np.where(u < app_share, "app", np.where(u < app_share + 0.15, "marketplace", "web"))
        dev_u = rng.random(n)
        device = np.where(channel == "app", "mobile",
                          np.where(dev_u < 0.42, "desktop", np.where(dev_u < 0.95, "mobile", "tablet")))

        # atrybucja kampanii (last click): wybór spośród aktywnych kampanii danego dnia
        campaign_id = np.full(n, -1)
        attributed = rng.random(n) < 0.42
        camp_start = pd.to_datetime(campaigns["start_date"]).values
        camp_end = pd.to_datetime(campaigns["end_date"]).values
        camp_w = np.where(campaigns["channel"] == "affiliate", 500,
                          np.where(campaigns["channel"] == "newsletter", 2500, campaigns["daily_budget"])).astype(float)
        camp_ids = campaigns["campaign_id"].values
        for day in np.unique(days.values):
            idx = np.where((days.values == day) & attributed)[0]
            if len(idx) == 0:
                continue
            active = (camp_start <= day) & (camp_end >= day)
            w = camp_w[active]
            campaign_id[idx] = rng.choice(camp_ids[active], len(idx), p=w / w.sum())

        pm, pp = PAYMENT
        payment = rng.choice(pm, n, p=pp)
        ship_methods = list(SHIPPING)
        ship = rng.choice(ship_methods, n, p=[SHIPPING[m][1] for m in ship_methods])
        payment = np.where((payment == "cash_on_delivery") & ~np.char.startswith(ship.astype(str), "courier"),
                           "blik", payment)
        # w czasie awarii prawie nie działa BLIK i karta
        outage = (days >= pd.Timestamp("2026-03-10")) & (days <= pd.Timestamp("2026-03-12"))
        payment = np.where(outage & np.isin(payment, ["blik", "card", "google_apple_pay"]),
                           rng.choice(["przelewy24", "cash_on_delivery", "paypo"], n), payment)

        status = np.where(rng.random(n) < 0.032, "cancelled", "delivered")
        status = np.where(outage & (rng.random(n) < 0.35), "cancelled", status)
        age_days = (self.end - days).days.values
        status = np.where((status != "cancelled") & (age_days <= 2), "processing", status)
        status = np.where((status != "cancelled") & (age_days > 2) & (age_days <= 6), "shipped", status)

        df = pd.DataFrame({
            "customer_id": order_customer,
            "_day": days,
            "order_ts": utc_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "_utc": utc_ts,
            "status": status,
            "channel": channel,
            "device": device,
            "campaign_id": campaign_id,
            "payment_method": payment,
            "shipping_method": ship,
        }).sort_values("_utc").reset_index(drop=True)
        df.insert(0, "order_id", np.arange(100001, 100001 + len(df)))
        return df

    # -- pozycje zamówień -------------------------------------------------
    def order_items(self, orders: pd.DataFrame, products: pd.DataFrame, campaigns: pd.DataFrame) -> pd.DataFrame:
        rng = self.rng
        n_items = np.minimum(1 + rng.poisson(0.55, len(orders)), 6)
        item_order = np.repeat(np.arange(len(orders)), n_items)
        item_month = orders["_day"].dt.to_period("M").to_numpy()[item_order]
        camp = campaigns.set_index("campaign_id")
        target = orders["campaign_id"].map(camp["target_category"]).values[item_order]
        target = pd.Series(target).fillna("").values

        prod_launch = pd.to_datetime(products["launched_at"]).values
        prod_cat = products["category"].values
        product_choice = np.empty(len(item_order), dtype=int)
        for (month, tgt), idx in pd.Series(np.arange(len(item_order))).groupby([item_month, target]).groups.items():
            m_end = month.to_timestamp(how="end")
            avail = prod_launch <= np.datetime64(m_end)
            season = np.array([SEASON[s][month.month - 1] for s in products["_season"]])
            w = products["_pop"].values * season * avail
            if tgt:
                w = w * np.where(prod_cat == tgt, 3.0, 1.0)
            product_choice[idx] = rng.choice(len(products), len(idx), p=w / w.sum())

        lp = products["list_price"].values[product_choice]
        qty = np.where(lp < 60, rng.choice([1, 2, 3, 4], len(lp), p=[0.62, 0.26, 0.08, 0.04]),
                       rng.choice([1, 2, 3], len(lp), p=[0.88, 0.10, 0.02]))
        items = pd.DataFrame({"_order_idx": item_order, "_prod_idx": product_choice, "quantity": qty})
        items = items.groupby(["_order_idx", "_prod_idx"], as_index=False)["quantity"].sum()

        o = orders.iloc[items["_order_idx"]]
        p = products.iloc[items["_prod_idx"]]
        t_years = ((o["_day"] - self.start).dt.days.values / 365.25)
        unit_price = price_99(p["list_price"].values * (1 + 0.045 * t_years))
        disc_rate = o["campaign_id"].map(camp["discount_pct"]).fillna(0).values
        disc_target = o["campaign_id"].map(camp["target_category"]).values
        applies = pd.isna(disc_target) | (disc_target == p["category"].values)
        discount = np.where(applies, disc_rate, 0.0)
        # sporadyczne rabaty produktowe (outlet)
        discount = np.where((discount == 0) & (rng.random(len(items)) < 0.06), 0.05, discount)

        items = pd.DataFrame({
            "order_id": o["order_id"].values,
            "product_id": p["product_id"].values,
            "quantity": items["quantity"].values,
            "unit_price": np.round(unit_price, 2),
            "discount_pct": np.round(discount, 2),
            "_category": p["category"].values,
            "_return_rate": p["_return_rate"].values,
            "_status": o["status"].values,
            "_day": o["_day"].values,
        }).sort_values(["order_id", "product_id"]).reset_index(drop=True)
        items.insert(0, "order_item_id", np.arange(1, len(items) + 1))
        return items

    # -- zwroty ----------------------------------------------------------
    def returns(self, items: pd.DataFrame) -> pd.DataFrame:
        rng = self.rng
        eligible = items["_status"].isin(["delivered"]).values
        is_ret = eligible & (rng.random(len(items)) < items["_return_rate"].values)
        r = items[is_ret].copy()
        delay = rng.integers(3, 31, len(r))
        r_day = pd.to_datetime(r["_day"]) + pd.to_timedelta(delay, unit="D")
        r = r[r_day <= self.end]
        r_day = r_day[r_day <= self.end]
        ret_qty = np.where(r["quantity"].values > 1,
                           rng.integers(1, r["quantity"].values + 1), 1)
        fashion = r["_category"].values == "Moda"
        reason = np.where(fashion,
                          rng.choice(RETURN_REASONS, len(r), p=RETURN_REASON_P_FASHION),
                          rng.choice(RETURN_REASONS, len(r), p=RETURN_REASON_P_OTHER))
        refund = np.round(ret_qty * r["unit_price"].values * (1 - r["discount_pct"].values), 2)
        out = pd.DataFrame({
            "order_item_id": r["order_item_id"].values,
            "return_date": r_day.dt.date.values,
            "returned_quantity": ret_qty,
            "reason": reason,
            "refund_amount": refund,
        }).sort_values("return_date").reset_index(drop=True)
        out.insert(0, "return_id", np.arange(1, len(out) + 1))
        return out

    # -- koszty marketingu ----------------------------------------------
    def marketing_spend(self, campaigns: pd.DataFrame, orders: pd.DataFrame, items: pd.DataFrame) -> pd.DataFrame:
        rng = self.rng
        cpm = {"google_ads": 22.0, "meta_ads": 14.0, "tiktok_ads": 9.0, "newsletter": 0.0, "affiliate": 0.0}
        ctr = {"google_ads": 0.031, "meta_ads": 0.012, "tiktok_ads": 0.008, "newsletter": 0.045, "affiliate": 0.02}
        net = items.assign(net=items["quantity"] * items["unit_price"] * (1 - items["discount_pct"]))
        rev = (net.groupby("order_id")["net"].sum().rename("rev").to_frame()
               .join(orders.set_index("order_id")[["campaign_id", "_day"]]))
        aff_rev = rev.groupby(["campaign_id", "_day"])["rev"].sum()

        rows = []
        for c in campaigns.itertuples():
            for day in pd.date_range(c.start_date, c.end_date):
                if c.channel == "affiliate":
                    spend = 0.08 * aff_rev.get((c.campaign_id, day), 0.0)
                    impressions = int(rng.integers(8000, 20000))
                elif c.channel == "newsletter":
                    spend = c.daily_budget
                    impressions = int(rng.integers(38000, 52000))  # wysłane e-maile
                else:
                    spend = c.daily_budget * WEEKDAY[day.weekday()] * rng.lognormal(0, 0.12)
                    impressions = int(spend / cpm[c.channel] * 1000 * rng.lognormal(0, 0.1))
                clicks = int(impressions * ctr[c.channel] * rng.lognormal(0, 0.15))
                rows.append({"date": day.date(), "campaign_id": c.campaign_id, "channel": c.channel,
                             "spend": round(spend, 2), "impressions": impressions, "clicks": clicks})
        df = pd.DataFrame(rows)
        # incydent 2: luka w eksporcie z Meta (brak danych za 5 dni)
        gap = (df["channel"] == "meta_ads") & (pd.to_datetime(df["date"]).between("2025-07-01", "2025-07-05"))
        return df[~gap].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Problemy z jakością danych (celowe)
# ---------------------------------------------------------------------------
def inject_quality_issues(rng, customers, orders, items, products, end):
    customers = customers.copy()
    orders = orders.copy()
    items = items.copy()
    products = products.copy()

    # 1) duplikaty klientów: ten sam e-mail inną wielkością liter / ze spacjami, późniejsza rejestracja
    n_dup = int(len(customers) * 0.015)
    src = customers.sample(n_dup, random_state=int(rng.integers(1e9)))
    dup = src.copy()
    next_id = customers["customer_id"].max() + 1
    dup["customer_id"] = np.arange(next_id, next_id + n_dup)
    dup["email"] = [("  " + e.upper()) if i % 2 else (e.capitalize() + " ") for i, e in enumerate(dup["email"])]
    new_signup = pd.to_datetime(dup["signup_date"]) + pd.to_timedelta(rng.integers(30, 300, n_dup), unit="D")
    dup["signup_date"] = np.minimum(new_signup, pd.Timestamp(end)).dt.date
    # część późniejszych zamówień oryginału trafia na zduplikowane konto
    mapping = dict(zip(src["customer_id"], zip(dup["customer_id"], pd.to_datetime(dup["signup_date"]))))
    for i, row in orders[orders["customer_id"].isin(mapping)].iterrows():
        dup_id, dup_signup = mapping[row["customer_id"]]
        if row["_day"] >= dup_signup and rng.random() < 0.5:
            orders.at[i, "customer_id"] = dup_id
    customers = pd.concat([customers, dup], ignore_index=True)

    # 2) konta testowe zespołu QA (do wykluczenia z raportów)
    qa_ids = np.arange(customers["customer_id"].max() + 1, customers["customer_id"].max() + 13)
    qa = pd.DataFrame({"customer_id": qa_ids, "first_name": "Test", "last_name": "QA",
                       "email": [f"qa+{i}@test.sklep.example" for i in range(len(qa_ids))],
                       "city": "Warszawa", "voivodeship": "mazowieckie",
                       "signup_date": pd.Timestamp("2025-01-15").date(), "acquisition_channel": "organic",
                       "birth_year": 1990, "gender": "M"})
    customers = pd.concat([customers, qa], ignore_index=True)
    sample = orders.sample(len(qa_ids) * 3, random_state=int(rng.integers(1e9))).index
    orders.loc[sample, "customer_id"] = np.repeat(qa_ids, 3)

    # 3) niespójne miasta i województwa
    u = rng.random(len(customers))
    city = customers["city"].astype(str)
    customers["city"] = np.select(
        [u < 0.04, u < 0.06, u < 0.08, u < 0.095],
        [city.str.lower(), city.str.upper(), city + " ", ""], city)
    v = rng.random(len(customers))
    customers["voivodeship"] = np.where(v < 0.03, customers["voivodeship"].str.upper(), customers["voivodeship"])

    # 4) zdublowane wiersze zamówień (błąd w procesie ETL)
    dups = orders.sample(frac=0.004, random_state=int(rng.integers(1e9)))
    orders = pd.concat([orders, dups]).sort_values("order_id").reset_index(drop=True)

    # 5) przecinek dziesiętny i zerowa ilość w pozycjach
    items["unit_price"] = items["unit_price"].map(lambda x: f"{x:.2f}")
    mask = rng.random(len(items)) < 0.01
    items.loc[mask, "unit_price"] = items.loc[mask, "unit_price"].str.replace(".", ",", regex=False)
    zero = rng.random(len(items)) < 0.001
    items.loc[zero, "quantity"] = 0

    # 6) spacje w nazwie kategorii
    m = rng.random(len(products)) < 0.03
    products.loc[m, "category"] = products.loc[m, "category"] + " "
    return customers, orders, items, products


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/raw", help="katalog wyjściowy")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--start", default="2024-10-01")
    ap.add_argument("--end", default="2026-09-30")
    ap.add_argument("--customers", type=int, default=12000)
    ap.add_argument("--base-orders", type=float, default=40.0, help="średnia liczba zamówień dziennie na starcie")
    ap.add_argument("--no-quality-issues", action="store_true", help="wyłącza celowe błędy w danych")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    g = Generator(args.seed, args.start, args.end, args.customers, args.base_orders)

    products = g.products()
    campaigns = g.campaigns()
    volume = g.daily_volume(campaigns)
    customers = g.customers(volume)
    orders = g.orders(customers, volume, campaigns)
    items = g.order_items(orders, products, campaigns)

    # koszt dostawy zależny od wartości koszyka
    basket = (items.assign(v=items["quantity"] * items["unit_price"] * (1 - items["discount_pct"]))
              .groupby("order_id")["v"].sum())
    base_cost = orders["shipping_method"].map({k: v[0] for k, v in SHIPPING.items()})
    orders["shipping_cost"] = np.where(orders["order_id"].map(basket) >= FREE_SHIPPING_THRESHOLD, 0.0, base_cost)

    returns = g.returns(items)
    # zamówienia zwrócone w całości dostają status "returned"
    ret_qty = returns.groupby("order_item_id")["returned_quantity"].sum()
    it = items.assign(rq=items["order_item_id"].map(ret_qty).fillna(0))
    fully = it.groupby("order_id").apply(lambda x: (x["rq"] >= x["quantity"]).all(), include_groups=False)
    orders.loc[orders["order_id"].isin(fully[fully].index), "status"] = "returned"

    spend = g.marketing_spend(campaigns, orders, items)

    if not args.no_quality_issues:
        customers, orders, items, products = inject_quality_issues(g.rng, customers, orders, items, products, args.end)

    orders["campaign_id"] = orders["campaign_id"].replace(-1, pd.NA).astype("Int64")
    write = {
        "customers": customers[[c for c in customers.columns if not c.startswith("_")]],
        "products": products[[c for c in products.columns if not c.startswith("_")]],
        "campaigns": campaigns.drop(columns=["lift_factor"]),
        "orders": orders[["order_id", "customer_id", "order_ts", "status", "channel", "device",
                          "campaign_id", "payment_method", "shipping_method", "shipping_cost"]],
        "order_items": items[["order_item_id", "order_id", "product_id", "quantity", "unit_price", "discount_pct"]],
        "returns": returns,
        "marketing_spend": spend,
    }
    total = 0
    for name, df in write.items():
        path = out / f"{name}.csv"
        df.to_csv(path, index=False, encoding="utf-8")
        size = path.stat().st_size
        total += size
        print(f"{name:<16} {len(df):>8,} wierszy  {size / 1e6:6.2f} MB")
    print(f"{'RAZEM':<16} {'':>8}         {total / 1e6:6.2f} MB  ->  {out.resolve()}")


if __name__ == "__main__":
    main()
