"""Shared pagination / sorting / search query-parameter dependency."""

from dataclasses import dataclass
from typing import Literal

from fastapi import Query


@dataclass(slots=True)
class PageParams:
    page: int
    page_size: int
    sort_by: str | None
    sort_order: Literal["asc", "desc"]
    search: str | None

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


def pagination_params(
    page: int = Query(1, ge=1, description="1-indexed page number"),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    sort_by: str | None = Query(None, alias="sortBy"),
    sort_order: Literal["asc", "desc"] = Query("desc", alias="sortOrder"),
    search: str | None = Query(None, min_length=1, max_length=255, alias="q"),
) -> PageParams:
    return PageParams(page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order, search=search)


def message_pagination_params(
    page: int = Query(1, ge=1, description="1-indexed page number"),
    page_size: int = Query(100, ge=1, le=200, alias="pageSize"),
    sort_by: str | None = Query(None, alias="sortBy"),
    sort_order: Literal["asc", "desc"] = Query("desc", alias="sortOrder"),
    search: str | None = Query(None, min_length=1, max_length=255, alias="q"),
) -> PageParams:
    """Chat message history loads more per page than other list views."""
    return PageParams(page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order, search=search)


def build_paginated_response(items: list, total: int, params: PageParams) -> dict:
    return {
        "items": items,
        "page": params.page,
        "pageSize": params.page_size,
        "total": total,
        "hasNextPage": params.offset + len(items) < total,
    }
