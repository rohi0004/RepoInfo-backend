"""/repositories endpoints."""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.pagination import PageParams, pagination_params
from app.models.user import User
from app.schemas.base import MessageResponse, PaginatedResponse, Success
from app.schemas.repository import (
    ArchitectureOverviewOut,
    DependencyGraphOut,
    ExportOut,
    ExportRequest,
    FileTreeNodeOut,
    RepositoryAddRequest,
    RepositoryMetricsOut,
    RepositoryOut,
    SecurityReportOut,
)
from app.services.repository_service import RepositoryService

router = APIRouter()


@router.get("", response_model=Success[PaginatedResponse[RepositoryOut]])
async def list_repositories(
    page: PageParams = Depends(pagination_params),
    pinned_only: bool = Query(False, alias="pinnedOnly"),
    favorites_only: bool = Query(False, alias="favoritesOnly"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = RepositoryService(db)
    items, total = await service.list(
        user,
        offset=page.offset,
        limit=page.limit,
        search=page.search,
        pinned_only=pinned_only,
        favorites_only=favorites_only,
        sort_by=page.sort_by or "updated_at",
        sort_order=page.sort_order,
    )
    return {
        "success": True,
        "data": {
            "items": [i.model_dump(by_alias=True) for i in items],
            "page": page.page,
            "pageSize": page.page_size,
            "total": total,
            "hasNextPage": page.offset + len(items) < total,
        },
    }


@router.post("", response_model=Success[RepositoryOut], status_code=status.HTTP_201_CREATED)
async def add_repository(
    payload: RepositoryAddRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    out = await RepositoryService(db).add(user, payload)
    await db.commit()
    return {"success": True, "data": out.model_dump(by_alias=True)}


@router.get("/search", response_model=Success[list[RepositoryOut]])
async def search_repositories(
    q: str = Query(min_length=1, max_length=255),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    items, _ = await RepositoryService(db).list(
        user,
        offset=0,
        limit=limit,
        search=q,
        pinned_only=False,
        favorites_only=False,
        sort_by="updated_at",
        sort_order="desc",
    )
    return {"success": True, "data": [i.model_dump(by_alias=True) for i in items]}


@router.get("/{repo_id}", response_model=Success[RepositoryOut])
async def get_repository(
    repo_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    out = await RepositoryService(db).get(user, repo_id)
    return {"success": True, "data": out.model_dump(by_alias=True)}


@router.delete("/{repo_id}", response_model=Success[MessageResponse])
async def delete_repository(
    repo_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await RepositoryService(db).delete(user, repo_id)
    await db.commit()
    return {"success": True, "data": {"message": "Repository deleted."}}


@router.post("/{repo_id}/process", response_model=Success[RepositoryOut])
async def reprocess_repository(
    repo_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    out = await RepositoryService(db).reprocess(user, repo_id)
    await db.commit()
    return {"success": True, "data": out.model_dump(by_alias=True)}


@router.get("/{repo_id}/tree", response_model=Success[list[FileTreeNodeOut]])
async def get_tree(
    repo_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    tree = await RepositoryService(db).get_tree(user, repo_id)
    return {"success": True, "data": [n.model_dump(by_alias=True) for n in tree]}


@router.get("/{repo_id}/architecture", response_model=Success[ArchitectureOverviewOut])
async def get_architecture(
    repo_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    out = await RepositoryService(db).get_architecture(user, repo_id)
    return {"success": True, "data": out.model_dump(by_alias=True)}


@router.get("/{repo_id}/dependencies", response_model=Success[DependencyGraphOut])
async def get_dependencies(
    repo_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    out = await RepositoryService(db).get_dependencies(user, repo_id)
    return {"success": True, "data": out.model_dump(by_alias=True)}


@router.get("/{repo_id}/security", response_model=Success[SecurityReportOut])
async def get_security(
    repo_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    out = await RepositoryService(db).get_security(user, repo_id)
    return {"success": True, "data": out.model_dump(by_alias=True)}


@router.get("/{repo_id}/metrics", response_model=Success[RepositoryMetricsOut])
async def get_metrics(
    repo_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    out = await RepositoryService(db).get_metrics(user, repo_id)
    return {"success": True, "data": out.model_dump(by_alias=True)}


@router.post("/{repo_id}/favorite", response_model=Success[RepositoryOut])
async def toggle_favorite(
    repo_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    out = await RepositoryService(db).toggle_favorite(user, repo_id)
    await db.commit()
    return {"success": True, "data": out.model_dump(by_alias=True)}


@router.post("/{repo_id}/pin", response_model=Success[RepositoryOut])
async def toggle_pin(
    repo_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    out = await RepositoryService(db).toggle_pin(user, repo_id)
    await db.commit()
    return {"success": True, "data": out.model_dump(by_alias=True)}


@router.post("/{repo_id}/export", response_model=Success[ExportOut])
async def request_export(
    repo_id: uuid.UUID,
    payload: ExportRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    out = await RepositoryService(db).request_export(user, repo_id, payload)
    await db.commit()
    return {"success": True, "data": out.model_dump(by_alias=True)}
