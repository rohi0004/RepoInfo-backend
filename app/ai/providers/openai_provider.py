"""OpenAI provider (also used for OpenRouter via base_url override)."""

from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.ai.providers.base import AIProvider, ChatChunk, ChatMessage, ChatUsage
from app.core.config import settings


class OpenAIProvider(AIProvider):
    name = "openai"
    default_model = "gpt-4o-mini"

    def __init__(self, *, api_key: str | None = None, base_url: str | None = None, name: str = "openai") -> None:
        self.name = name
        self._client = AsyncOpenAI(
            api_key=api_key or settings.OPENAI_API_KEY or "sk-noop",
            base_url=base_url,
        )

    async def stream_chat(
        self,
        *,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> AsyncIterator[ChatChunk]:
        stream = await self._client.chat.completions.create(
            model=model or self.default_model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            stream_options={"include_usage": True},
        )
        prompt_tokens = completion_tokens = 0
        finish_reason: str | None = None
        async for event in stream:
            if event.usage is not None:
                prompt_tokens = event.usage.prompt_tokens
                completion_tokens = event.usage.completion_tokens
            for choice in event.choices:
                delta = choice.delta.content or ""
                if choice.finish_reason:
                    finish_reason = choice.finish_reason
                if delta:
                    yield ChatChunk(delta=delta)
        yield ChatChunk(
            done=True,
            finish_reason=finish_reason,
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
        resp = await self._client.chat.completions.create(
            model=model or self.default_model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = resp.choices[0].message.content or ""
        usage = ChatUsage(
            prompt_tokens=resp.usage.prompt_tokens if resp.usage else 0,
            completion_tokens=resp.usage.completion_tokens if resp.usage else 0,
            total_tokens=resp.usage.total_tokens if resp.usage else 0,
        )
        return content, usage

    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        resp = await self._client.embeddings.create(
            model=model or "text-embedding-3-small", input=texts
        )
        return [item.embedding for item in resp.data]
