"""Retrieval-Augmented Generation agent.

Given a user query and repository context, it:
1. Embeds the query.
2. Queries Milvus for top-K semantic chunks.
3. Assembles a system + context + history prompt.
4. Streams the response back through the selected provider.

Callers get an async iterator of `ChatChunk` — same contract used by SSE endpoints.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass

from loguru import logger

from app.ai.embeddings.service import embedding_service
from app.ai.prompts.library import build_context_message, build_system_message
from app.ai.providers import ChatChunk, ChatMessage, get_provider, is_provider_unavailable
from app.core.config import settings
from app.models.enums import AIProviderEnum
from app.vectorstore.milvus_client import milvus_client


def _provider_chain(requested: AIProviderEnum | None) -> list[AIProviderEnum]:
    """Primary provider first, then the configured fallback order (deduplicated)."""
    chain = [requested or AIProviderEnum(settings.DEFAULT_AI_PROVIDER)]
    for raw in settings.AI_PROVIDER_FALLBACK_ORDER:
        try:
            kind = AIProviderEnum(raw.strip())
        except ValueError:
            continue
        if kind not in chain:
            chain.append(kind)
    return chain


@dataclass(slots=True)
class RagContext:
    repository_id: str
    repository_full_name: str
    primary_language: str | None = None
    active_branch: str | None = None
    history: list[ChatMessage] | None = None


class RagAgent:
    async def stream(
        self,
        *,
        question: str,
        ctx: RagContext,
        provider: AIProviderEnum | None = None,
        model: str | None = None,
        temperature: float = 0.3,
        top_k: int = 8,
    ) -> AsyncIterator[ChatChunk]:
        question = question.strip()
        query_embeddings: list[list[float]] = []
        try:
            query_embeddings = await embedding_service.embed_texts([question])
        except Exception as exc:
            if not is_provider_unavailable(exc):
                raise
            logger.warning(f"Embedding provider unavailable, skipping retrieval context: {exc}")
        chunks: list[dict] = []
        if query_embeddings:
            chunks = milvus_client.search(
                collection=settings.MILVUS_COLLECTION_CHUNKS,
                embedding=query_embeddings[0],
                repository_id=ctx.repository_id,
                top_k=top_k,
            )

        messages: list[ChatMessage] = [
            ChatMessage(role="system", content=build_system_message(ctx.repository_full_name)),
        ]
        if chunks:
            messages.append(
                ChatMessage(
                    role="system",
                    content=build_context_message(
                        repository_full_name=ctx.repository_full_name,
                        primary_language=ctx.primary_language,
                        active_branch=ctx.active_branch,
                        chunks=chunks,
                    ),
                )
            )
        if ctx.history:
            messages.extend(ctx.history)
        messages.append(ChatMessage(role="user", content=question))

        provider_chain = _provider_chain(provider)
        for idx, kind in enumerate(provider_chain):
            provider_impl = get_provider(kind)
            started = False
            try:
                async for chunk in provider_impl.stream_chat(
                    messages=messages,
                    model=model if idx == 0 else None,
                    temperature=temperature,
                ):
                    started = True
                    if chunk.done:
                        chunk.raw["provider"] = kind.value
                    yield chunk
                return
            except Exception as exc:
                is_last = idx == len(provider_chain) - 1
                if started or is_last or not is_provider_unavailable(exc):
                    raise
                logger.warning(
                    f"AI provider '{kind.value}' unavailable, falling back to "
                    f"'{provider_chain[idx + 1].value}': {exc}"
                )


rag_agent = RagAgent()
