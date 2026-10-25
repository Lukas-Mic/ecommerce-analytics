"""Asystent analityczny: pytanie po polsku -> SQL (Claude) -> wynik z hurtowni -> komentarz.

Bezpieczeństwo (warstwowo):
  1. połączenie jako bi_reader: tylko SELECT, tylko schemat marts, transakcje tylko do odczytu,
  2. walidacja: jedno zapytanie SELECT/WITH, bez średników i komentarzy,
  3. limit czasu zapytania i limit wierszy (zapytanie opakowane w SELECT ... LIMIT),
  4. limity pytań: na adres IP na godzinę i globalny na dobę (koszt API pod kontrolą).
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from collections import defaultdict, deque
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from . import context

log = logging.getLogger("asystent")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

MODEL_SQL = os.getenv("MODEL_SQL", "claude-sonnet-5-5")
MODEL_SUMMARY = os.getenv("MODEL_SUMMARY", "claude-haiku-5-5")
HOURLY_LIMIT_PER_IP = int(os.getenv("HOURLY_LIMIT_PER_IP", "15"))
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", "100"))
MAX_ROWS = int(os.getenv("MAX_ROWS", "500"))
STATEMENT_TIMEOUT_MS = int(os.getenv("STATEMENT_TIMEOUT_MS", "8000"))
MAX_QUESTION_CHARS = 400
SQL_MAX_TOKENS = int(os.getenv("SQL_MAX_TOKENS", "8000"))
SUMMARY_MAX_TOKENS = int(os.getenv("SUMMARY_MAX_TOKENS", "3000"))  # z zapasem na myślenie modelu
SUMMARY_MAX_CHARS = 14000  # ok. 4-5 tys. tokenów danych dla modelu komentującego
LOG_PATH = Path(os.getenv("LOG_PATH", "/data/logs/questions.jsonl"))
STATIC_DIR = Path(__file__).parent / "static"


# --------------------------------------------------------------------------- baza
def _pg_query(sql: str, params: tuple | None = None):
    import psycopg  # import tutaj, żeby testy mogły podmienić warstwę bazy

    with psycopg.connect(
        host=os.getenv("DB_HOST", "postgres"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "warehouse"),
        user=os.getenv("DB_USER", "bi_reader"),
        password=os.getenv("DB_PASSWORD", ""),
        connect_timeout=5,
    ) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute(f"set local statement_timeout = {STATEMENT_TIMEOUT_MS}")
            cur.execute(sql, params)
            columns = [d.name for d in cur.description] if cur.description else []
            return columns, cur.fetchall()


run_query = _pg_query


# --------------------------------------------------------------------------- model
def _anthropic_call(model: str, system: str, user: str, max_tokens: int):
    import anthropic

    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        # Modele 5.5 nie przyjmują temperature/top_p/top_k.
    )
    # Odpowiedź może zawierać bloki "thinking" - bierzemy tylko tekst.
    # Myślenie wlicza się do max_tokens, więc przy zbyt niskim limicie tekst bywa pusty.
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    if not text.strip():
        log.warning("Pusta odpowiedź modelu %s (stop_reason=%s, output_tokens=%s)",
                    model, resp.stop_reason, resp.usage.output_tokens)
    usage = {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens}
    return text, usage


call_model = _anthropic_call


# --------------------------------------------------------------------------- walidacja
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|merge|drop|alter|create|truncate|grant|revoke|copy|call|do|"
    r"vacuum|analyze|refresh|listen|notify|set|reset|lock|pg_sleep|pg_read|lo_import|dblink)\b",
    re.IGNORECASE,
)


OTHER_SCHEMAS = re.compile(r"\b(raw|staging|intermediate|public|pg_catalog|information_schema)\s*\.",
                           re.IGNORECASE)


class SqlRejected(ValueError):
    pass


def validate_sql(sql: str) -> str:
    s = (sql or "").strip().rstrip(";").strip()
    if not s:
        raise SqlRejected("Puste zapytanie.")
    if ";" in s:
        raise SqlRejected("Dozwolone jest tylko jedno zapytanie.")
    if "--" in s or "/*" in s:
        raise SqlRejected("Komentarze w SQL są niedozwolone.")
    if not re.match(r"^(select|with)\b", s, re.IGNORECASE):
        raise SqlRejected("Dozwolone są tylko zapytania SELECT.")
    # słowa kluczowe poza literałami tekstowymi
    without_strings = re.sub(r"'(?:[^']|'')*'", "''", s)
    without_idents = re.sub(r'"(?:[^"]|"")*"', '""', without_strings)
    bad = FORBIDDEN.search(without_idents)
    if bad:
        raise SqlRejected(f"Niedozwolona operacja: {bad.group(0).upper()}.")
    other_schema = OTHER_SCHEMAS.search(without_idents)
    if other_schema:
        raise SqlRejected(f"Dostępna jest tylko warstwa raportowa (marts), nie {other_schema.group(1)}.")
    return s


def parse_model_json(text: str) -> dict:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    start, end = t.find("{"), t.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Model nie zwrócił JSON.")
    return json.loads(t[start:end + 1])


# --------------------------------------------------------------------------- limity
class RateLimiter:
    def __init__(self):
        self.lock = threading.Lock()
        self.per_ip: dict[str, deque] = defaultdict(deque)
        self.day = date.today()
        self.day_count = 0

    def check(self, ip: str) -> str | None:
        now = time.time()
        with self.lock:
            if date.today() != self.day:
                self.day, self.day_count = date.today(), 0
            q = self.per_ip[ip]
            while q and now - q[0] > 3600:
                q.popleft()
            if self.day_count >= DAILY_LIMIT:
                return "Dzienny limit pytań do asystenta został wyczerpany. Zapraszam jutro."
            if len(q) >= HOURLY_LIMIT_PER_IP:
                return f"Limit {HOURLY_LIMIT_PER_IP} pytań na godzinę. Spróbuj za chwilę."
            q.append(now)
            self.day_count += 1
            return None


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    # Za Caddy: ostatni wpis X-Forwarded-For dopisuje nasz proxy (wcześniejsze można podrobić).
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[-1].strip()
    return request.client.host if request.client else "?"


# --------------------------------------------------------------------------- logika
_schema_cache: dict[str, str] = {}


def schema_text() -> str:
    if "schema" not in _schema_cache:
        _schema_cache["schema"] = context.build_schema(run_query)
        log.info("Schemat załadowany: %d znaków", len(_schema_cache["schema"]))
    return _schema_cache["schema"]


def to_json_value(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return v


def execute(sql: str):
    wrapped = f"select * from (\n{sql}\n) as wynik limit {MAX_ROWS + 1}"
    columns, rows = run_query(wrapped)
    truncated = len(rows) > MAX_ROWS
    rows = [[to_json_value(v) for v in r] for r in rows[:MAX_ROWS]]
    return columns, rows, truncated


def summary_rows(columns, rows, max_chars: int = SUMMARY_MAX_CHARS) -> int:
    """Ile wierszy zmieści się w podglądzie dla modelu komentującego (limit znaków JSON)."""
    size = len(json.dumps(columns, ensure_ascii=False)) + 40
    for i, r in enumerate(rows):
        size += len(json.dumps(r, ensure_ascii=False, default=str)) + 1
        if size > max_chars:
            return max(i, 1)
    return len(rows)


def answer(question: str) -> dict:
    system = context.SYSTEM_PROMPT.format(rules=context.BUSINESS_RULES, schema=schema_text())
    usage_total = {"input_tokens": 0, "output_tokens": 0}

    def add(u):
        for k in usage_total:
            usage_total[k] += u.get(k, 0)

    prompt = f"Pytanie: {question}"
    plan, last_error = None, None
    for attempt in range(2):  # druga próba z komunikatem błędu z bazy
        text, usage = call_model(MODEL_SQL, system, prompt, SQL_MAX_TOKENS)
        add(usage)
        plan = parse_model_json(text)
        if not plan.get("sql"):
            return {"message": plan.get("message") or "Nie potrafię odpowiedzieć na to pytanie.",
                    "usage": usage_total, "model": MODEL_SQL}
        try:
            sql = validate_sql(plan["sql"])
            columns, rows, truncated = execute(sql)
            break
        except SqlRejected:
            raise
        except Exception as e:  # błąd bazy -> jedna poprawka
            last_error = str(e).strip().splitlines()[0][:400]
            log.info("Błąd SQL (próba %d): %s", attempt + 1, last_error)
            prompt = (f"Pytanie: {question}\n\nTwoje poprzednie zapytanie:\n{plan['sql']}\n\n"
                      f"zwróciło błąd PostgreSQL:\n{last_error}\n\nPopraw zapytanie.")
    else:
        raise RuntimeError(f"Nie udało się wykonać zapytania: {last_error}")

    summary = None
    if rows:
        shown = summary_rows(columns, rows)
        preview = json.dumps({"kolumny": columns, "wiersze": rows[:shown]}, ensure_ascii=False, default=str)
        note = (f"pełny wynik, {len(rows)} wierszy" if shown == len(rows)
                else f"pierwsze {shown} z {len(rows)} wierszy - komentuj ostrożnie, nie znasz całości")
        try:
            summary, usage = call_model(
                MODEL_SUMMARY, context.SUMMARY_PROMPT,
                f"Pytanie: {question}\nZapytanie SQL:\n{sql}\nWynik ({note}):\n{preview}",
                SUMMARY_MAX_TOKENS)
            add(usage)
            summary = summary.strip() or None
        except Exception as e:  # komentarz jest dodatkiem - wynik i tak pokazujemy
            log.warning("Komentarz niedostępny: %s", e)

    return {
        "title": plan.get("title"),
        "sql": sql,
        "assumptions": plan.get("assumptions"),
        "chart": plan.get("chart"),
        "columns": columns,
        "rows": rows,
        "truncated": truncated,
        "summary": summary,
        "model": MODEL_SQL,
        "usage": usage_total,
    }


def write_log(entry: dict):
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as e:
        log.warning("Nie zapisano logu: %s", e)


# --------------------------------------------------------------------------- HTTP
async def ask(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Nieprawidłowe żądanie."}, status_code=400)
    question = str(body.get("question", "")).strip()
    if not question:
        return JSONResponse({"error": "Wpisz pytanie."}, status_code=400)
    if len(question) > MAX_QUESTION_CHARS:
        return JSONResponse({"error": f"Pytanie może mieć maks. {MAX_QUESTION_CHARS} znaków."}, status_code=400)
    if not os.getenv("ANTHROPIC_API_KEY") and call_model is _anthropic_call:
        return JSONResponse({"error": "Asystent nie ma skonfigurowanego klucza API."}, status_code=503)

    limit_msg = limiter.check(client_ip(request))
    if limit_msg:
        return JSONResponse({"error": limit_msg}, status_code=429)

    t0 = time.time()
    entry = {"ts": datetime.now().isoformat(timespec="seconds"), "question": question}
    try:
        import anyio
        result = await anyio.to_thread.run_sync(answer, question)
        result["elapsed_ms"] = int((time.time() - t0) * 1000)
        entry.update(ok=True, sql=result.get("sql"), rows=len(result.get("rows") or []),
                     usage=result.get("usage"), ms=result["elapsed_ms"])
        return JSONResponse(result)
    except SqlRejected as e:
        entry.update(ok=False, error=f"odrzucone: {e}")
        return JSONResponse({"error": f"Wygenerowane zapytanie zostało odrzucone. {e}"}, status_code=422)
    except Exception as e:
        log.exception("Błąd odpowiedzi")
        entry.update(ok=False, error=str(e)[:300])
        return JSONResponse({"error": "Nie udało się odpowiedzieć na pytanie. Spróbuj sformułować je inaczej."},
                            status_code=500)
    finally:
        write_log(entry)


async def health(request: Request):
    return JSONResponse({"status": "ok", "model": MODEL_SQL})


async def index(request: Request):
    return FileResponse(STATIC_DIR / "index.html")


app = Starlette(routes=[
    Route("/", index),
    Route("/api/ask", ask, methods=["POST"]),
    Route("/api/health", health),
    Mount("/static", StaticFiles(directory=STATIC_DIR), name="static"),
])
