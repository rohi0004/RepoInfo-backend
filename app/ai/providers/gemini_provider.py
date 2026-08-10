"""Google Gemini provider (via google-generativeai)."""

from collections.abc import AsyncIterator

import google.generativeai as genai

from app.ai.providers.base import AIProvider, ChatChunk, ChatMessage, ChatUsage
from app.core.config import settings


class GeminiProvider(AIProvider):
    name = "gemini"
    default_model = "gemini-1.5-flash"

    def __init__(self, api_key: str | None = None) -> None:
        genai.configure(api_key=api_key or settings.GEMINI_API_KEY or "noop")

    def _to_contents(self, messages: list[ChatMessage]) -> tuple[str, list[dict]]:
        system_parts = [m.content for m in messages if m.role == "system"]
        contents = []
        for m in messages:
            if m.role == "system":
                continue
            contents.append({"role": "user" if m.role == "user" else "model", "parts": [m.content]})
        return "\n\n".join(system_parts), contents

    async def stream_chat(
        self,
        *,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> AsyncIterator[ChatChunk]:
        system, contents = self._to_contents(messages)
        gen_model = genai.GenerativeModel(
            model_name=model or self.default_model,
            system_instruction=system or None,
            generation_config={"temperature": temperature, "max_output_tokens": max_tokens or 4096},
        )
        stream = await gen_model.generate_content_async(contents, stream=True)
        prompt_tokens = completion_tokens = 0
        async for event in stream:
            if event.text:
                yield ChatChunk(delta=event.text)
            if getattr(event, "usage_metadata", None):
                prompt_tokens = event.usage_metadata.prompt_token_count
                completion_tokens = event.usage_metadata.candidates_token_count
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
        system, contents = self._to_contents(messages)
        gen_model = genai.GenerativeModel(
            model_name=model or self.default_model,
            system_instruction=system or None,
            generation_config={"temperature": temperature, "max_output_tokens": max_tokens or 4096},
        )
        resp = await gen_model.generate_content_async(contents)
        prompt_tokens = resp.usage_metadata.prompt_token_count if resp.usage_metadata else 0
        completion_tokens = (
            resp.usage_metadata.candidates_token_count if resp.usage_metadata else 0
        )
        return resp.text or "", ChatUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )

    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        results: list[list[float]] = []
        for text in texts:
            r = await genai.embed_content_async(model=model or "models/text-embedding-004", content=text)
            results.append(r["embedding"])
        return results
