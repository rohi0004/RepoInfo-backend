#!/usr/bin/env bash
# Convenience dev bootstrapper: brings up infra, runs migrations, seeds data,
# and starts uvicorn with reload.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
    cp .env.development .env
fi

docker compose -f docker/docker-compose.yml up -d postgres redis elasticsearch

echo "Waiting for Postgres..."
until docker compose -f docker/docker-compose.yml exec -T postgres pg_isready -U repoinfo >/dev/null 2>&1; do
    sleep 1
done

echo "Running Alembic migrations..."
alembic upgrade head

echo "Seeding data..."
python -m scripts.seed

echo "Starting API..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
