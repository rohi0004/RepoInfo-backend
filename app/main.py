"""FastAPI application entrypoint.

Wires up:
- Global middlewares (CORS, security headers, request context, CSRF, rate limiting).
- Global exception handlers producing the frontend's `ApiError` envelope.
- API v1 routers.
- Prometheus /metrics + Sentry (opt-in).
- Lifespan hooks (Redis / DB / storage / vector / search warm-up + graceful close).
"""

from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import ORJSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi.errors import RateLimitExceeded

from app import __version__
from app.api.v1 import api_router
from app.core.config import settings
from app.core.error_handlers import register_exception_handlers
from app.core.logging import configure_logging, logger
from app.core.redis import close_redis_connections, redis_cache
from app.database.session import engine
from app.middlewares import (
    CSRFMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
    limiter,
    rate_limit_exceeded_handler,
)
from app.search.elasticsearch_client import es_client
from app.storage.s3_client import s3_client
from app.vectorstore.milvus_client import milvus_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info(f"Starting {settings.APP_NAME} v{__version__} in {settings.APP_ENV}")

    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.APP_ENV,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            send_default_pii=False,
        )

    try:
        await redis_cache.ping()
        logger.info("Redis connection OK")
    except Exception as exc:
        logger.warning(f"Redis connection failed at startup: {exc}")

    try:
        await s3_client.ensure_bucket()
        logger.info("Storage bucket ensured")
    except Exception as exc:
        logger.warning(f"Storage warm-up failed: {exc}")

    try:
        await es_client.ensure_indices()
        logger.info("Elasticsearch indices ensured")
    except Exception as exc:
        logger.warning(f"Elasticsearch warm-up failed: {exc}")

    try:
        milvus_client.ensure_collections()
        logger.info("Milvus collections ensured")
    except Exception as exc:
        logger.warning(f"Milvus warm-up failed: {exc}")

    yield

    logger.info("Shutting down application")
    await close_redis_connections()
    await engine.dispose()
    await es_client.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=__version__,
        default_response_class=ORJSONResponse,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
    )
    if settings.is_production and settings.ALLOWED_HOSTS != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CSRFMiddleware)
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        return {
            "name": settings.APP_NAME,
            "version": __version__,
            "environment": settings.APP_ENV,
            "docs": "/docs" if not settings.is_production else None,
        }

    @app.get("/health", tags=["health"])
    async def health() -> dict:
        return {"status": "ok", "version": __version__}

    @app.get("/ready", tags=["health"])
    async def ready() -> dict:
        checks: dict[str, str] = {}
        try:
            await redis_cache.ping()
            checks["redis"] = "ok"
        except Exception as exc:
            checks["redis"] = f"error: {exc}"
        return {"status": "ready", "checks": checks}

    if settings.PROMETHEUS_ENABLED:
        Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

    return app


app = create_app()
