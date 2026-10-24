FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv

COPY requirements.txt .
RUN pip install -r requirements.txt \
    && useradd --create-home --uid 10001 asystent \
    && mkdir -p /data/logs && chown asystent /data/logs

COPY app ./app
# Chart.js serwowany lokalnie (bez zależności od CDN w przeglądarce)
ADD https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js ./app/static/chart.umd.min.js
RUN chmod 644 ./app/static/chart.umd.min.js
USER asystent
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
