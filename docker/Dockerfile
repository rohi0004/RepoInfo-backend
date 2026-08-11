# syntax=docker/dockerfile:1.6
FROM python:3.13-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        build-essential \
        curl \
        ca-certificates \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# ---- deps layer ----
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# ---- app layer ----
COPY . .

RUN chmod +x docker/entrypoint.sh && \
    adduser --disabled-password --gecos "" appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["docker/entrypoint.sh"]
