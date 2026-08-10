"""Search API schemas covering repository/file/function/semantic search."""

from typing import Literal

from pydantic import Field

from app.schemas.base import CamelBaseModel

SearchScope = Literal["repositories", "code", "functions", "files", "semantic"]


class SearchQuery(CamelBaseModel):
    q: str = Field(min_length=1, max_length=500)
    scope: SearchScope = "repositories"
    repository_id: str | None = None
    language: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class SearchHit(CamelBaseModel):
    id: str
    scope: SearchScope
    repository_id: str | None = None
    title: str
    snippet: str
    score: float
    file_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None


class SearchResponse(CamelBaseModel):
    hits: list[SearchHit]
    total: int
    took_ms: int
