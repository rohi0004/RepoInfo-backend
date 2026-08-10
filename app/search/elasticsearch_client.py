"""Async Elasticsearch wrapper: index management, indexing, multi-scope search.

Kept optional at boot: connection failures are logged as warnings so the app
still starts in development without Elasticsearch running (search endpoints
degrade gracefully to an empty result set)."""

from typing import Any

from elasticsearch import AsyncElasticsearch
from elasticsearch import exceptions as es_exceptions

from app.core.config import settings
from app.core.logging import logger


REPO_MAPPING: dict[str, Any] = {
    "properties": {
        "repository_id": {"type": "keyword"},
        "full_name": {"type": "text", "fields": {"kw": {"type": "keyword"}}},
        "name": {"type": "text"},
        "description": {"type": "text"},
        "primary_language": {"type": "keyword"},
        "topics": {"type": "keyword"},
        "stars": {"type": "integer"},
        "updated_at": {"type": "date"},
    }
}

FILE_MAPPING: dict[str, Any] = {
    "properties": {
        "repository_id": {"type": "keyword"},
        "file_id": {"type": "keyword"},
        "path": {"type": "text", "fields": {"kw": {"type": "keyword"}}},
        "name": {"type": "text"},
        "language": {"type": "keyword"},
        "content": {"type": "text"},
        "lines_of_code": {"type": "integer"},
    }
}

FUNCTION_MAPPING: dict[str, Any] = {
    "properties": {
        "repository_id": {"type": "keyword"},
        "file_id": {"type": "keyword"},
        "path": {"type": "keyword"},
        "name": {"type": "text"},
        "signature": {"type": "text"},
        "body": {"type": "text"},
        "language": {"type": "keyword"},
        "line_start": {"type": "integer"},
        "line_end": {"type": "integer"},
    }
}


class ElasticsearchClient:
    def __init__(self) -> None:
        auth = None
        if settings.ELASTICSEARCH_USERNAME and settings.ELASTICSEARCH_PASSWORD:
            auth = (settings.ELASTICSEARCH_USERNAME, settings.ELASTICSEARCH_PASSWORD)
        self._client = AsyncElasticsearch(
            hosts=[settings.ELASTICSEARCH_URL], basic_auth=auth, request_timeout=30
        )

    @property
    def client(self) -> AsyncElasticsearch:
        return self._client

    async def close(self) -> None:
        try:
            await self._client.close()
        except Exception:
            pass

    async def ensure_indices(self) -> None:
        for idx, mapping in (
            (settings.ELASTICSEARCH_REPO_INDEX, REPO_MAPPING),
            (settings.ELASTICSEARCH_FILE_INDEX, FILE_MAPPING),
            (settings.ELASTICSEARCH_FUNCTION_INDEX, FUNCTION_MAPPING),
        ):
            try:
                exists = await self._client.indices.exists(index=idx)
                if not exists:
                    await self._client.indices.create(index=idx, mappings=mapping)
                    logger.info(f"Created Elasticsearch index: {idx}")
            except es_exceptions.ConnectionError as exc:
                logger.warning(f"Elasticsearch not reachable: {exc}")
                return

    async def index_repository(self, repo_id: str, body: dict) -> None:
        try:
            await self._client.index(
                index=settings.ELASTICSEARCH_REPO_INDEX, id=repo_id, document=body
            )
        except es_exceptions.ElasticsearchException as exc:
            logger.warning(f"Failed to index repo {repo_id}: {exc}")

    async def index_files(self, docs: list[dict]) -> None:
        if not docs:
            return
        body: list[dict] = []
        for doc in docs:
            body.append({"index": {"_index": settings.ELASTICSEARCH_FILE_INDEX, "_id": doc.get("file_id")}})
            body.append(doc)
        try:
            await self._client.bulk(operations=body)
        except es_exceptions.ElasticsearchException as exc:
            logger.warning(f"Bulk file index failed: {exc}")

    async def delete_by_repository(self, repo_id: str) -> None:
        query = {"term": {"repository_id": repo_id}}
        for idx in (
            settings.ELASTICSEARCH_REPO_INDEX,
            settings.ELASTICSEARCH_FILE_INDEX,
            settings.ELASTICSEARCH_FUNCTION_INDEX,
        ):
            try:
                await self._client.delete_by_query(index=idx, query=query, conflicts="proceed")
            except es_exceptions.ElasticsearchException as exc:
                logger.warning(f"Delete by repo failed on {idx}: {exc}")

    async def search(
        self, *, scope: str, q: str, repository_id: str | None = None, limit: int = 20
    ) -> dict:
        index = {
            "repositories": settings.ELASTICSEARCH_REPO_INDEX,
            "code": settings.ELASTICSEARCH_FILE_INDEX,
            "files": settings.ELASTICSEARCH_FILE_INDEX,
            "functions": settings.ELASTICSEARCH_FUNCTION_INDEX,
            "semantic": settings.ELASTICSEARCH_FILE_INDEX,  # vector search happens via Milvus
        }.get(scope, settings.ELASTICSEARCH_REPO_INDEX)

        must: list[dict] = [{"multi_match": {"query": q, "fields": ["*"], "type": "best_fields"}}]
        filters: list[dict] = []
        if repository_id and scope != "repositories":
            filters.append({"term": {"repository_id": repository_id}})

        try:
            response = await self._client.search(
                index=index,
                query={"bool": {"must": must, "filter": filters}},
                size=limit,
                highlight={"fields": {"*": {}}},
            )
            return response.body if hasattr(response, "body") else dict(response)
        except es_exceptions.ConnectionError:
            return {"hits": {"total": {"value": 0}, "hits": []}, "took": 0}
        except es_exceptions.ElasticsearchException as exc:
            logger.warning(f"ES search error: {exc}")
            return {"hits": {"total": {"value": 0}, "hits": []}, "took": 0}


es_client = ElasticsearchClient()
