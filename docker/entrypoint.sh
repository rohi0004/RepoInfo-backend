#!/usr/bin/env bash
# Runs pending Alembic migrations, then hands off to gunicorn. Used by
# docker-compose, Railway, Render, Fly.io, Cloud Run, etc.
#
# $PORT is provided by Render/Cloud Run/Heroku; defaults to 8000 locally.
# $WEB_CONCURRENCY tunes gunicorn workers; keep it low (2) on 512 MB free
# tiers to avoid OOM, raise to 4 on larger hosts.
set -euo pipefail

: "${PORT:=8000}"
: "${WEB_CONCURRENCY:=2}"

echo "Running Alembic migrations..."
alembic upgrade head || {
  echo "WARN: Alembic migrations failed — continuing to boot the API anyway."
  echo "      Fix POSTGRES_* env vars if this repeats."
}

echo "Starting API on 0.0.0.0:${PORT} with ${WEB_CONCURRENCY} workers..."
exec gunicorn app.main:app \
    -k uvicorn.workers.UvicornWorker \
    -w "${WEB_CONCURRENCY}" \
    -b "0.0.0.0:${PORT}" \
    --timeout 120 \
    --graceful-timeout 30 \
    --access-logfile - \
    --error-logfile -
