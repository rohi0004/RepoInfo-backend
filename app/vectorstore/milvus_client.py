"""Milvus vector-store wrapper.

Manages 3 logical collections (chunks / files / docs), each keyed by
(repository_id, source_type, source_path, chunk_index). Uses cosine similarity
over IVF_FLAT indexes; parameters are conservative defaults good enough for
low-latency lookups up to ~10M vectors.
"""

from typing import Any

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

from app.core.config import settings
from app.core.logging import logger


class MilvusClient:
    def __init__(self) -> None:
        self.alias = "default"
        self._connected = False

    def connect(self) -> None:
        if self._connected:
            return
        try:
            connections.connect(
                alias=self.alias,
                host=settings.MILVUS_HOST,
                port=str(settings.MILVUS_PORT),
                user=settings.MILVUS_USER or None,
                password=settings.MILVUS_PASSWORD or None,
            )
            self._connected = True
        except Exception as exc:
            logger.warning(f"Milvus connection failed: {exc}")

    def _schema(self) -> CollectionSchema:
        dim = settings.EMBEDDING_DIMENSION
        return CollectionSchema(
            fields=[
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="repository_id", dtype=DataType.VARCHAR, max_length=64),
                FieldSchema(name="source_type", dtype=DataType.VARCHAR, max_length=32),
                FieldSchema(name="source_path", dtype=DataType.VARCHAR, max_length=1024),
                FieldSchema(name="chunk_index", dtype=DataType.INT64),
                FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=8192),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
            ],
            description="RepoInfo semantic index",
        )

    def _ensure_collection(self, name: str) -> Collection:
        if not utility.has_collection(name, using=self.alias):
            col = Collection(name=name, schema=self._schema(), using=self.alias)
            col.create_index(
                field_name="embedding",
                index_params={
                    "index_type": "IVF_FLAT",
                    "metric_type": "COSINE",
                    "params": {"nlist": 1024},
                },
            )
            logger.info(f"Created Milvus collection: {name}")
        col = Collection(name=name, using=self.alias)
        try:
            col.load()
        except Exception as exc:
            logger.warning(f"Milvus load failed for {name}: {exc}")
        return col

    def ensure_collections(self) -> None:
        self.connect()
        if not self._connected:
            return
        for name in (
            settings.MILVUS_COLLECTION_CHUNKS,
            settings.MILVUS_COLLECTION_FILES,
            settings.MILVUS_COLLECTION_DOCS,
        ):
            self._ensure_collection(name)

    def insert(
        self,
        *,
        collection: str,
        repository_id: str,
        source_type: str,
        source_path: str,
        chunk_index: int,
        content: str,
        embedding: list[float],
    ) -> int | None:
        self.connect()
        if not self._connected:
            return None
        col = self._ensure_collection(collection)
        try:
            result = col.insert(
                [
                    [repository_id],
                    [source_type],
                    [source_path],
                    [chunk_index],
                    [content[:8000]],
                    [embedding],
                ]
            )
            col.flush()
            return int(result.primary_keys[0])
        except Exception as exc:
            logger.warning(f"Milvus insert failed: {exc}")
            return None

    def search(
        self,
        *,
        collection: str,
        embedding: list[float],
        repository_id: str | None = None,
        top_k: int = 8,
    ) -> list[dict[str, Any]]:
        self.connect()
        if not self._connected:
            return []
        col = self._ensure_collection(collection)
        try:
            expr = f'repository_id == "{repository_id}"' if repository_id else None
            results = col.search(
                data=[embedding],
                anns_field="embedding",
                param={"metric_type": "COSINE", "params": {"nprobe": 16}},
                limit=top_k,
                expr=expr,
                output_fields=["repository_id", "source_type", "source_path", "chunk_index", "content"],
            )
            hits: list[dict[str, Any]] = []
            for row in results:
                for hit in row:
                    hits.append(
                        {
                            "score": float(hit.distance),
                            "repository_id": hit.entity.get("repository_id"),
                            "source_type": hit.entity.get("source_type"),
                            "source_path": hit.entity.get("source_path"),
                            "chunk_index": hit.entity.get("chunk_index"),
                            "content": hit.entity.get("content"),
                        }
                    )
            return hits
        except Exception as exc:
            logger.warning(f"Milvus search failed: {exc}")
            return []

    def delete_by_repository(self, collection: str, repository_id: str) -> None:
        self.connect()
        if not self._connected:
            return
        try:
            col = self._ensure_collection(collection)
            col.delete(expr=f'repository_id == "{repository_id}"')
        except Exception as exc:
            logger.warning(f"Milvus delete failed: {exc}")


milvus_client = MilvusClient()
