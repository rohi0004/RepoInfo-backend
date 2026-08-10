"""Search service unifying Elasticsearch keyword search and Milvus semantic search."""

import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings.service import embedding_service
from app.core.config import settings
from app.models.user import User
from app.schemas.search import SearchHit, SearchQuery, SearchResponse
from app.search.elasticsearch_client import es_client
from app.vectorstore.milvus_client import milvus_client


class SearchService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def search(self, user: User, query: SearchQuery) -> SearchResponse:  # noqa: ARG002
        started = time.perf_counter()
        if query.scope == "semantic":
            vectors = await embedding_service.embed_texts([query.q])
            if not vectors:
                return SearchResponse(hits=[], total=0, took_ms=0)
            raw = milvus_client.search(
                collection=settings.MILVUS_COLLECTION_CHUNKS,
                embedding=vectors[0],
                repository_id=query.repository_id,
                top_k=query.limit,
            )
            hits = [
                SearchHit(
                    id=f"{r['source_path']}#{r['chunk_index']}",
                    scope="semantic",
                    repository_id=r.get("repository_id"),
                    title=r["source_path"],
                    snippet=r["content"][:400],
                    score=r["score"],
                    file_path=r["source_path"],
                )
                for r in raw
            ]
            return SearchResponse(
                hits=hits,
                total=len(hits),
                took_ms=int((time.perf_counter() - started) * 1000),
            )

        raw = await es_client.search(
            scope=query.scope,
            q=query.q,
            repository_id=query.repository_id,
            limit=query.limit,
        )
        hits_body = raw.get("hits", {}).get("hits", [])
        hits: list[SearchHit] = []
        for h in hits_body:
            src = h.get("_source", {})
            snippet = ""
            highlight = h.get("highlight", {})
            for _, values in highlight.items():
                if values:
                    snippet = " ".join(values)[:400]
                    break
            hits.append(
                SearchHit(
                    id=h.get("_id"),
                    scope=query.scope,
                    repository_id=src.get("repository_id"),
                    title=src.get("full_name") or src.get("path") or src.get("name") or "",
                    snippet=snippet or (src.get("description") or "")[:400],
                    score=float(h.get("_score") or 0),
                    file_path=src.get("path"),
                    line_start=src.get("line_start"),
                    line_end=src.get("line_end"),
                )
            )
        total = raw.get("hits", {}).get("total", {})
        total_value = total.get("value", 0) if isinstance(total, dict) else int(total or 0)
        return SearchResponse(
            hits=hits,
            total=total_value,
            took_ms=int((time.perf_counter() - started) * 1000),
        )
