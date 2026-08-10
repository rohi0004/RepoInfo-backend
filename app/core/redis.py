"""Shared async Redis connection pools (cache, rate limiting)."""

from redis.asyncio import ConnectionPool, Redis

from app.core.config import settings

_cache_pool = ConnectionPool.from_url(settings.REDIS_CACHE_URL, decode_responses=True, max_connections=50)
_rate_limit_pool = ConnectionPool.from_url(
    settings.RATE_LIMIT_REDIS_URL, decode_responses=True, max_connections=50
)

redis_cache = Redis(connection_pool=_cache_pool)
redis_rate_limit = Redis(connection_pool=_rate_limit_pool)


async def get_redis_cache() -> Redis:
    return redis_cache


async def close_redis_connections() -> None:
    await redis_cache.aclose()
    await redis_rate_limit.aclose()
