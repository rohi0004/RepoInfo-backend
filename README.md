# RepoInfo Backend

Enterprise-grade backend for the **RepoInfo** AI-powered repository analysis platform.

- FastAPI + Python 3.13
- PostgreSQL + SQLAlchemy 2 (async) + Alembic
- Redis (cache + broker + rate limits + pub/sub)
- MinIO (object storage), Elasticsearch (keyword search), Milvus (vector search)
- Celery + Beat (analysis, embeddings, exports, email, cleanup)
- Multi-provider AI (Anthropic Claude, OpenAI, Google Gemini, Ollama, OpenRouter)
- Prometheus + Grafana metrics, Sentry error tracking, Loguru structured logs
- JWT auth (with refresh-token rotation & reuse detection), Google + GitHub OAuth
- Docker + docker-compose (dev + prod), Nginx reverse proxy with HTTPS + SSE + WS

---

## Table of contents

1. [Architecture](#architecture)
2. [Folder structure](#folder-structure)
3. [Requirements](#requirements)
4. [Quick start (Docker)](#quick-start-docker)
5. [Quick start (bare metal)](#quick-start-bare-metal)
6. [Environment variables](#environment-variables)
7. [Database setup](#database-setup)
8. [Running the workers](#running-the-workers)
9. [OAuth setup](#oauth-setup)
10. [AI providers](#ai-providers)
11. [Testing](#testing)
12. [Deployment](#deployment)
13. [Frontend integration](#frontend-integration)

---

## Architecture

```
┌────────────────┐        ┌────────────────┐
│  React (Vite)  │──HTTPS─▶│     Nginx      │
└────────────────┘        └───────┬────────┘
                                  │reverse proxy + SSE/WS
                                  ▼
                          ┌────────────────┐
                          │  FastAPI API   │──JWT, RBAC, rate limiting
                          └─┬────┬────┬────┘
             ┌──────────────┘    │    └────────────────────┐
             ▼                   ▼                         ▼
      ┌───────────┐        ┌───────────┐            ┌────────────┐
      │ Postgres  │        │  Redis    │──broker───▶│  Celery    │
      │ (SQLA2)   │        │ (cache +  │            │  workers   │
      └───────────┘        │  pub/sub) │            │ + beat     │
                           └───────────┘            └────┬───────┘
                                                        │
                          ┌───────────┬─────────────────┴───────┐
                          ▼           ▼                         ▼
                    ┌──────────┐┌──────────┐            ┌────────────┐
                    │  MinIO   ││   ES     │            │   Milvus   │
                    │ objects  ││ keyword  │            │  vectors   │
                    └──────────┘└──────────┘            └────────────┘
```

- **API** (this repo): request/response, auth, RBAC, streams, orchestrates services.
- **Workers**: repository cloning + analysis pipeline, embeddings, exports, email.
- **Beat**: periodic cleanups + usage rollups.
- **Nginx**: HTTPS termination, compression, SSE + WebSocket passthrough.

---

## Folder structure

```
backend/
├── app/
│   ├── main.py                    ← FastAPI entrypoint (lifespan, CORS, routers)
│   ├── api/v1/                    ← Every REST endpoint mounted here
│   ├── core/                      ← config, security, exceptions, logging, redis
│   ├── database/                  ← Base + engine + session + type helpers
│   ├── dependencies/              ← FastAPI dependencies (auth, pagination)
│   ├── events/                    ← SSE writer, Redis pub/sub
│   ├── middlewares/               ← rate_limit, csrf, security_headers, request_context
│   ├── models/                    ← SQLAlchemy ORM models
│   ├── permissions/               ← RBAC permission-check dependency
│   ├── repositories/              ← Data-access layer (one per aggregate)
│   ├── schemas/                   ← Pydantic v2 request/response models (camelCase)
│   ├── services/                  ← Business logic (auth, chat, repo, billing…)
│   ├── search/                    ← Elasticsearch wrapper + index mappings
│   ├── storage/                   ← MinIO async wrapper
│   ├── vectorstore/               ← Milvus client + schema/index management
│   ├── ai/
│   │   ├── providers/             ← Claude, OpenAI, Gemini, Ollama, OpenRouter
│   │   ├── prompts/               ← Prompt library + Jinja renderer
│   │   ├── embeddings/            ← Chunker + provider + Milvus persistence
│   │   └── agents/                ← RAG agent (retrieve → prompt → stream)
│   ├── workers/
│   │   ├── celery_app.py          ← Celery config + Beat schedule + queues
│   │   └── tasks/                 ← repository, embeddings, security, export, email, cleanup
│   ├── templates/emails/          ← Jinja2 email templates
│   └── utils/                     ← email, git helpers
├── migrations/                    ← Alembic (single initial revision)
├── docker/                        ← Dockerfile(.dev), compose (dev + prod), nginx, prometheus
├── scripts/                       ← dev.sh, seed.py, reset_db.py
├── tests/                         ← Pytest suite (SQLite in-memory by default)
├── alembic.ini
├── pyproject.toml
├── requirements.txt / requirements-dev.txt
├── .env.example / .env.development / .env.production / .env.test
└── README.md (you are here)
```

---

## Requirements

- **Docker Desktop 4.30+** (with Compose v2) — recommended path.
- Or **Python 3.13** + local Postgres/Redis/MinIO/Elasticsearch/Milvus if running bare-metal.

---

## Quick start (Docker)

```bash
cd backend

# 1. copy the example env; edit as needed
cp .env.example .env

# 2. bring the whole stack up (api + worker + beat + postgres + redis + minio + es + milvus + nginx)
docker compose -f docker/docker-compose.yml up -d --build

# 3. run database migrations
docker compose -f docker/docker-compose.yml exec api alembic upgrade head

# 4. seed roles/permissions/plans/demo admin
docker compose -f docker/docker-compose.yml exec api python -m scripts.seed
```

Once the stack is up:

- API: <http://localhost:8000> (docs at `/docs`, health at `/health`, metrics at `/metrics`)
- MinIO console: <http://localhost:9001> (user `repoinfo_admin` / pw `repoinfo_secret_key`)
- Flower (Celery): <http://localhost:5555>
- Prometheus: <http://localhost:9090>
- Grafana: <http://localhost:3001>

---

## Quick start (bare metal)

```bash
cd backend
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# Start Postgres/Redis/MinIO/Elasticsearch/Milvus separately (see docker-compose for images).
cp .env.development .env

alembic upgrade head
python -m scripts.seed
uvicorn app.main:app --reload
```

Then in another shell for background jobs:

```bash
celery -A app.workers.celery_app.celery_app worker --loglevel=INFO -Q default,analysis,embeddings,email,exports
celery -A app.workers.celery_app.celery_app beat --loglevel=INFO
```

---

## Environment variables

See [`.env.example`](.env.example) for the exhaustive list. Grouped by concern:

| Group          | Keys                                                                 |
|----------------|----------------------------------------------------------------------|
| App            | `APP_ENV`, `DEBUG`, `SECRET_KEY`, `BACKEND_BASE_URL`, `FRONTEND_BASE_URL`, `CORS_ORIGINS`, `ALLOWED_HOSTS` |
| Database       | `POSTGRES_*`, `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`          |
| Redis          | `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`                         |
| JWT            | `JWT_*`, `OTP_*`, `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES`              |
| OAuth          | `GOOGLE_*`, `GITHUB_*`                                               |
| Rate limits    | `RATE_LIMIT_DEFAULT`, `RATE_LIMIT_AUTH`, `RATE_LIMIT_AI`              |
| MinIO          | `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_SECURE`, bucket names |
| Elasticsearch  | `ELASTICSEARCH_URL`, `ELASTICSEARCH_USERNAME`, `ELASTICSEARCH_PASSWORD` |
| Milvus         | `MILVUS_HOST`, `MILVUS_PORT`, `EMBEDDING_DIMENSION`                  |
| AI             | `DEFAULT_AI_PROVIDER`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, `OLLAMA_BASE_URL` |
| Email          | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_TLS`   |
| Billing        | `STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET`, price IDs                 |
| Observability  | `SENTRY_DSN`, `LOG_LEVEL`, `LOG_JSON`, `PROMETHEUS_ENABLED`          |
| Encryption     | `API_KEY_ENCRYPTION_SECRET`                                          |

`SECRET_KEY` and `API_KEY_ENCRYPTION_SECRET` **must be at least 32 characters** and **must be regenerated for production**. Generate with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

---

## Database setup

The schema is managed by Alembic. A single **initial revision** at `migrations/versions/0001_initial_schema.py` builds every table via `Base.metadata.create_all()` and installs the `pgcrypto` + `pg_trgm` extensions.

```bash
alembic upgrade head              # apply migrations
alembic revision --autogenerate -m "add …"   # after model changes
alembic downgrade -1              # roll back the latest revision
python -m scripts.seed            # roles/permissions/plans/demo admin
python -m scripts.reset_db        # DEV ONLY — drops & recreates
```

**Default admin user seeded by `scripts.seed`:**

- Email: `admin@repoinfo.dev`
- Password: `ChangeMe!123`
- Role: `super_admin`

Change the password immediately in a non-local environment.

---

## Running the workers

```bash
# analysis + embeddings + email + exports queues
celery -A app.workers.celery_app.celery_app worker \
  --loglevel=INFO -Q default,analysis,embeddings,email,exports --concurrency=4

# scheduled tasks (OTP + export cleanup, daily usage rollup)
celery -A app.workers.celery_app.celery_app beat --loglevel=INFO
```

Task queues can be split across processes — e.g. run `embeddings` on a GPU box and `analysis` on a fast-CPU box.

---

## OAuth setup

### Google

1. Create OAuth client at <https://console.cloud.google.com/apis/credentials>.
2. Add authorized redirect URI: `http://localhost:8000/api/v1/auth/oauth/google/callback`.
3. Copy client ID + secret into `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`.

### GitHub

1. Create OAuth app at <https://github.com/settings/developers>.
2. Set the authorization callback URL to `http://localhost:8000/api/v1/auth/oauth/github/callback`.
3. Copy client ID + secret into `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET`.

The frontend redirects users to `GET /api/v1/auth/oauth/<provider>` (which returns the authorization URL) and then handles the callback route on its side; our server redirects back to `${FRONTEND_BASE_URL}/auth/oauth-callback?accessToken=…&refreshToken=…&expiresAt=…`.

---

## AI providers

Pick your default via `DEFAULT_AI_PROVIDER` (`claude` | `openai` | `gemini` | `openrouter` | `ollama`). Providers are lazily instantiated; you only need to set the API key(s) you actually use.

- **Claude**: `ANTHROPIC_API_KEY`
- **OpenAI**: `OPENAI_API_KEY`
- **Gemini**: `GEMINI_API_KEY`
- **OpenRouter**: `OPENROUTER_API_KEY` (routed through the OpenAI-compatible endpoint)
- **Ollama** (local): set `OLLAMA_BASE_URL=http://localhost:11434`, no API key needed

Embeddings default to `text-embedding-3-small` (OpenAI) or `models/text-embedding-004` (Gemini) or `nomic-embed-text` (Ollama). Milvus is created with a matching `EMBEDDING_DIMENSION`; leave the default `1536` unless you swap the model.

---

## Testing

The unit-test suite runs against an in-memory SQLite database, so it needs zero infrastructure:

```bash
pytest --cov=app
```

The integration tests inside `tests/` will use the Postgres/Redis services if `INTEGRATION=1` is set.

---

## Deployment

For production:

1. Fill in `.env.production` with secure secrets (rotate `SECRET_KEY` and `API_KEY_ENCRYPTION_SECRET`).
2. Place TLS certificates in `backend/docker/certs/` as `fullchain.pem` + `privkey.pem` (or point Nginx to your existing chain).
3. `docker compose -f docker/docker-compose.prod.yml up -d --build`
4. `docker compose -f docker/docker-compose.prod.yml exec api alembic upgrade head`
5. Point DNS at the Nginx host; requests hit `https://api.example.com` and are proxied to `api:8000`.

Recommended:

- Use a managed Postgres (RDS, Cloud SQL, Supabase) for durability.
- Terminate TLS at your load balancer if you have one, and drop the internal Nginx `ssl_certificate` block.
- Send logs to your log aggregator; the app already emits structured JSON when `LOG_JSON=true`.

---

## Frontend integration

The API keeps the exact contracts consumed by `frontend/src/api/endpoints.ts` and `frontend/src/services/*`:

- **Envelope**: every JSON response is `{ success, data, message? }`.
- **Errors**: `{ success: false, message, code, errors?, statusCode }`.
- **Casing**: wire keys are `camelCase`, matching the TS types.
- **Tokens**: `POST /auth/login` returns `{ user, tokens: { accessToken, refreshToken, expiresAt } }`.
- **Refresh**: `POST /auth/refresh` accepts `{ refreshToken }` and returns fresh tokens.
- **Streaming**: `POST /chat/conversations/{id}/messages` and `.../stream` return SSE (`event: start|delta|reference|usage|done|error`).

Point the frontend's `VITE_API_BASE_URL` at `http://localhost:8000/api/v1` and it will Just Work.
