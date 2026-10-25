"""Testy asystenta: walidator SQL i pełny przebieg na prawdziwej hurtowni z atrapą modelu.

Uruchomienie (wymaga zbudowanej hurtowni i zmiennych DB_*):
    python -m unittest discover -s assistant/tests -v
"""
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("LOG_PATH", "/tmp/asystent-test.jsonl")

from app import main  # noqa: E402
from app.main import SqlRejected, validate_sql  # noqa: E402


class TestValidator(unittest.TestCase):
    def test_allowed(self):
        for sql in [
            "select 1;",
            "WITH a AS (select 1) select * from a",
            'select count(*) as "Kto zrobił update" from marts.fct_orders',
            "select 'drop table' as t",
        ]:
            with self.subTest(sql=sql):
                validate_sql(sql)

    def test_rejected(self):
        for sql in [
            "select 1; drop table marts.fct_orders",
            "delete from marts.fct_orders",
            "update marts.dim_date set year = 1",
            "select pg_sleep(30)",
            "select * from raw.customers",
            "select * from staging.stg_customers",
            "select * from pg_catalog.pg_authid",
            "select 1 -- komentarz",
            "copy marts.fct_orders to stdout",
            "",
        ]:
            with self.subTest(sql=sql), self.assertRaises(SqlRejected):
                validate_sql(sql)


def fake_model(sql):
    def call(model, system, user, max_tokens):
        if model == main.MODEL_SUMMARY:
            return "Komentarz testowy.", {"input_tokens": 1, "output_tokens": 1}
        plan = {"title": "t", "sql": sql, "assumptions": "a",
                "chart": {"type": "bar", "x": "Kategoria", "y": ["Przychód"]}}
        return "```json\n" + json.dumps(plan, ensure_ascii=False) + "\n```", {"input_tokens": 1, "output_tokens": 1}
    return call


class TestSummaryPreview(unittest.TestCase):
    def test_small_result_fully_shown(self):
        self.assertEqual(main.summary_rows(["a", "b"], [[1, 2]] * 10), 10)

    def test_large_result_truncated_to_limit(self):
        rows = [["2026-04-01", "Dom i ogród", "app", 278, 404, 105288.26, 102081.97, 47555.12, 0.4659]] * 300
        n = main.summary_rows(["c"] * 9, rows)
        self.assertTrue(0 < n < 300)
        self.assertLessEqual(len(json.dumps(rows[:n], ensure_ascii=False)), main.SUMMARY_MAX_CHARS)


@unittest.skipUnless(os.getenv("DB_PASSWORD"), "brak połączenia z hurtownią")
class TestEndToEnd(unittest.TestCase):
    def test_schema_context(self):
        text = main.schema_text()
        self.assertIn("marts.fct_orders", text)
        self.assertIn("Elektronika", text)  # przykładowe wartości kategorii
        self.assertNotIn("raw.", text)

    def test_answer_runs_real_query(self):
        main.call_model = fake_model(
            'select p.category as "Kategoria", round(sum(i.net_amount), 2) as "Przychód" '
            "from marts.fct_order_items i join marts.dim_products p using (product_id) "
            "where not i.is_cancelled group by 1 order by 2 desc")
        result = main.answer("Przychód wg kategorii")
        self.assertEqual(result["columns"], ["Kategoria", "Przychód"])
        self.assertEqual(len(result["rows"]), 7)
        self.assertAlmostEqual(sum(r[1] for r in result["rows"]), 16026992.44, places=0)
        self.assertEqual(result["summary"], "Komentarz testowy.")

    def test_database_blocks_writes_even_if_validator_missed(self):
        for sql in ["create temp table t as select 1",       # transakcja tylko do odczytu
                    "delete from marts.dim_date",            # brak uprawnień do zapisu
                    "select * from marts.fct_orders limit 1 for update"]:
            with self.subTest(sql=sql), self.assertRaises(Exception):
                main.run_query(sql)
        with self.assertRaises(Exception):
            main.run_query("select count(*) from raw.orders")  # brak uprawnień do raw


if __name__ == "__main__":
    unittest.main()
