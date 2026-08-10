"""Server-Sent Events helpers.

Format follows the standard `event: <name>\ndata: <json>\n\n`. The frontend can
subscribe with `EventSource` and dispatch on the `event` name.
"""

from collections.abc import AsyncIterator
from typing import Any

import orjson
from starlette.responses import StreamingResponse

SSE_HEADERS: dict[str, str] = {
    "Cache-Control": "no-cache, no-transform",
    "Content-Type": "text/event-stream",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",  # disable nginx response buffering
}


def sse_event(event: str, data: dict[str, Any] | list[Any] | str | int | float) -> bytes:
    payload = data if isinstance(data, str) else orjson.loads(orjson.dumps(data))
    body = payload if isinstance(payload, str) else orjson.dumps(payload).decode()
    return f"event: {event}\ndata: {body}\n\n".encode("utf-8")


def sse_response(gen: AsyncIterator[bytes]) -> StreamingResponse:
    return StreamingResponse(gen, media_type="text/event-stream", headers=SSE_HEADERS)
