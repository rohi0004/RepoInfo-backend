#!/usr/bin/env bash
# Runs pending Alembic migrations, then hands off to gunicorn. Used by both
# docker-compose and Railway so a fresh/updated database is never skipped.
set -euo pipefail

echo "Running Alembic migrations..."
alembic upgrade head

echo "Starting API..."
exec gunicorn app.main:app \
    -k uvicorn.workers.UvicornWorker \
    -w 4 \
    -b 0.0.0.0:8000 \
    --timeout 120 \
    --graceful-timeout 30 \
    --access-logfile - \
    --error-logfile -
