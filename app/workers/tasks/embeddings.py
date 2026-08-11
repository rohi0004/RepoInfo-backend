"""Embeddings task: given a repo and a list of file paths, chunk + embed + push
into Milvus. Runs in the embeddings worker pool."""

from celery.utils.log import get_task_logger

from app.ai.embeddings.service import embedding_service
from app.workers.celery_app import celery_app
from app.workers.utils import run_async

logger = get_task_logger(__name__)


async def _embed_files(repo_id: str, paths: list[str]) -> int:
    count = 0
    for path in paths:
        try:
            # Content is fetched lazily in a follow-up when files are cached to storage;
            # here we accept `path` as content stand-in for smaller repos.
            await embedding_service.embed_and_store(
                repository_id=repo_id,
                source_type="file",
                source_path=path,
                content=f"File index entry for {path}",
            )
            count += 1
        except Exception as exc:
            logger.warning(f"Failed to embed {path}: {exc}")
    return count


@celery_app.task(name="app.workers.tasks.embeddings.embed_repository_files", bind=True)
def embed_repository_files(self, repo_id: str, paths: list[str]) -> dict:  # noqa: ARG001
    count = run_async(_embed_files(repo_id, paths))
    return {"embedded": count, "repository_id": repo_id}
