"""Utilities for Celery tasks: sync loop bridge for our async DB APIs, and a
context-manager style helper that publishes stage progress to Redis so the
frontend can subscribe over SSE.
"""

import asyncio
from collections.abc import Awaitable
from typing import TypeVar

T = TypeVar("T")

_worker_loop: asyncio.AbstractEventLoop | None = None


def run_async(coro: Awaitable[T]) -> T:
    """Run an awaitable on one persistent event loop per Celery worker process."""
    global _worker_loop

    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_loop)

    return _worker_loop.run_until_complete(coro)