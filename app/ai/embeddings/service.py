"""Embedding service: text-chunker + provider embed + Milvus persistence.

Chunking strategy: token-approximate windowing with a small overlap. We use
`tiktoken`'s `cl100k_base` for length estimation regardless of provider, which
gives us predictable chunk sizes without needing per-provider tokenizer support.
"""

from dataclasses import dataclass

import tiktoken

from app.ai.providers import get_provider
from app.core.config import settings
from app.models.enums import AIProviderEnum
from app.vectorstore.milvus_client import milvus_client

_encoder = tiktoken.get_encoding("cl100k_base")


@dataclass(slots=True)
class Chunk:
    source_path: str
    source_type: str
    chunk_index: int
    content: str
    token_count: int


def chunk_text(text: str, *, max_tokens: int = 512, overlap: int = 64) -> list[str]:
    tokens = _encoder.encode(text)
    if not tokens:
        return []
    chunks: list[str] = []
    step = max_tokens - overlap
    for start in range(0, len(tokens), step):
        window = tokens[start : start + max_tokens]
        chunks.append(_encoder.decode(window))
        if start + max_tokens >= len(tokens):
            break
    return chunks


class EmbeddingService:
    def __init__(self, provider_kind: AIProviderEnum | None = None) -> None:
        self._provider = get_provider(provider_kind or AIProviderEnum(settings.DEFAULT_AI_PROVIDER))

    async def embed_texts(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        return await self._provider.embed(texts, model=model)

    async def embed_and_store(
        self,
        *,
        repository_id: str,
        source_type: str,
        source_path: str,
        content: str,
        collection: str | None = None,
        model: str | None = None,
    ) -> list[int]:
        collection = collection or settings.MILVUS_COLLECTION_CHUNKS
        pieces = chunk_text(content)
        if not pieces:
            return []
        vectors = await self._provider.embed(pieces, model=model)
        primary_keys: list[int] = []
        for idx, (piece, vector) in enumerate(zip(pieces, vectors, strict=True)):
            pk = milvus_client.insert(
                collection=collection,
                repository_id=repository_id,
                source_type=source_type,
                source_path=source_path,
                chunk_index=idx,
                content=piece,
                embedding=vector,
            )
            if pk is not None:
                primary_keys.append(pk)
        return primary_keys


embedding_service = EmbeddingService()
