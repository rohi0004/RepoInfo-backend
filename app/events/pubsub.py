"""Redis pub/sub wrapper for cross-worker realtime broadcasts.

Used by:
- Celery tasks: publish `analysis:<repo_id>` progress ticks.
- SSE/WS endpoints: subscribe to a channel and forward events to the client.
"""

from collections.abc import AsyncIterator
from typing import Any

import orjson
from redis.asyncio import Redis

from app.core.redis import redis_cache


class RedisPubSub:
    def __init__(self, client: Redis) -> None:
        self._client = client

    async def publish(self, channel: str, payload: dict[str, Any]) -> None:
        await self._client.publish(channel, orjson.dumps(payload).decode())

    async def subscribe(self, channel: str) -> AsyncIterator[dict[str, Any]]:
        pubsub = self._client.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message is None or message.get("type") != "message":
                    continue
                data = message.get("data")
                if isinstance(data, bytes):
                    data = data.decode()
                if isinstance(data, str):
                    try:
                        yield orjson.loads(data)
                    except orjson.JSONDecodeError:
                        yield {"raw": data}
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()


redis_pubsub = RedisPubSub(redis_cache)
