"""Ollama (local) provider using its native HTTP streaming API."""

from collections.abc import AsyncIterator

import httpx
import orjson

from app.ai.providers.base import AIProvider, ChatChunk, ChatMessage, ChatUsage
from app.core.config import settings


class OllamaProvider(AIProvider):
    name = "ollama"
    default_model = "llama3.2"

    def __init__(self, base_url: str | None = None) -> None:
        self._base = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")

    async def stream_chat(
        self,
        *,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> AsyncIterator[ChatChunk]:
        payload = {
            "model": model or self.default_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "options": {"temperature": temperature, "num_predict": max_tokens or 4096},
        }
        prompt_tokens = completion_tokens = 0
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", f"{self._base}/api/chat", json=payload) as resp:
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    data = orjson.loads(line)
                    if data.get("done"):
                        prompt_tokens = data.get("prompt_eval_count", 0)
                        completion_tokens = data.get("eval_count", 0)
                        break
                    delta = data.get("message", {}).get("content", "")
                    if delta:
                        yield ChatChunk(delta=delta)
        yield ChatChunk(
            done=True,
            usage=ChatUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )

    async def complete(
        self,
        *,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> tuple[str, ChatUsage]:
        payload = {
            "model": model or self.default_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens or 4096},
        }
        async with httpx.AsyncClient(timeout=None) as client:
            resp = await client.post(f"{self._base}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)
        return data.get("message", {}).get("content", ""), ChatUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )

    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        results: list[list[float]] = []
        async with httpx.AsyncClient(timeout=None) as client:
            for text in texts:
                resp = await client.post(
                    f"{self._base}/api/embeddings",
                    json={"model": model or "nomic-embed-text", "prompt": text},
                )
                resp.raise_for_status()
                results.append(resp.json()["embedding"])
        return results
