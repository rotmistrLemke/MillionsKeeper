# ── Stage 1: builder ──────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Системные зависимости для TA-Lib и asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    wget \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# TA-Lib C library
RUN wget -q https://downloads.sourceforge.net/project/ta-lib/ta-lib/0.4.0/ta-lib-0.4.0-src.tar.gz \
    && tar -xzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib \
    && ./configure --prefix=/usr/local \
    && make -j$(nproc) \
    && make install \
    && cd .. \
    && rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# Python зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: runtime ──────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Только runtime системные либы
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# TA-Lib shared library из builder
COPY --from=builder /usr/local/lib/libta_lib* /usr/local/lib/
COPY --from=builder /usr/local/include/ta-lib /usr/local/include/ta-lib
RUN ldconfig

# Python пакеты из builder
COPY --from=builder /install /usr/local

# Исходный код
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

# NOTE: MetaTrader5 Python API работает только нативно на Windows.
# Этот Dockerfile предназначен для Linux-деплоя БЕЗ MT5 (только API/DB слой).
# Для торговли backend запускается нативно на Windows.

# Web-only entrypoint (без MT5, без агентов)
COPY web/ ./web/

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/docs')" || exit 1

CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
