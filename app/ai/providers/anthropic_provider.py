"""Anthropic (Claude) provider."""

from collections.abc import AsyncIterator

from anthropic import AsyncAnthropic

from app.ai.providers.base import AIProvider, ChatChunk, ChatMessage, ChatUsage
from app.core.config import settings


class AnthropicProvider(AIProvider):
    name = "claude"
    default_model = "claude-3-5-sonnet-latest"

    def __init__(self, api_key: str | None = None) -> None:
        self._client = AsyncAnthropic(api_key=api_key or settings.ANTHROPIC_API_KEY or "noop")

    def _split_system(self, messages: list[ChatMessage]) -> tuple[str, list[dict]]:
        system_parts = [m.content for m in messages if m.role == "system"]
        chat = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]
        return "\n\n".join(system_parts), chat

    async def stream_chat(
        self,
        *,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> AsyncIterator[ChatChunk]:
        system, chat = self._split_system(messages)
        prompt_tokens = completion_tokens = 0
        finish_reason: str | None = None
        async with self._client.messages.stream(
            model=model or self.default_model,
            system=system or None,
            messages=chat,
            temperature=temperature,
            max_tokens=max_tokens or 4096,
        ) as stream:
            async for text in stream.text_stream:
                if text:
                    yield ChatChunk(delta=text)
            final = await stream.get_final_message()
            if final.usage is not None:
                prompt_tokens = final.usage.input_tokens
                completion_tokens = final.usage.output_tokens
            finish_reason = final.stop_reason
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
        system, chat = self._split_system(messages)
        resp = await self._client.messages.create(
            model=model or self.default_model,
            system=system or None,
            messages=chat,
            temperature=temperature,
            max_tokens=max_tokens or 4096,
        )
        content = "".join(block.text for block in resp.content if getattr(block, "text", None))
        usage = ChatUsage(
            prompt_tokens=resp.usage.input_tokens,
            completion_tokens=resp.usage.output_tokens,
            total_tokens=resp.usage.input_tokens + resp.usage.output_tokens,
        )
        return content, usage
