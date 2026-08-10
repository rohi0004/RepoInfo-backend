"""/projects endpoints."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.pagination import PageParams, pagination_params
from app.models.user import User
from app.schemas.base import MessageResponse, PaginatedResponse, Success
from app.schemas.project import ProjectCreateRequest, ProjectOut, ProjectUpdateRequest
from app.services.project_service import ProjectService

router = APIRouter()


@router.get("", response_model=Success[PaginatedResponse[ProjectOut]])
async def list_projects(
    page: PageParams = Depends(pagination_params),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    items, total = await ProjectService(db).list(user, offset=page.offset, limit=page.limit)
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


@router.post("", response_model=Success[ProjectOut], status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    out = await ProjectService(db).create(user, payload)
    await db.commit()
    return {"success": True, "data": out.model_dump(by_alias=True)}


@router.patch("/{project_id}", response_model=Success[ProjectOut])
async def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    out = await ProjectService(db).update(user, project_id, payload)
    await db.commit()
    return {"success": True, "data": out.model_dump(by_alias=True)}


@router.delete("/{project_id}", response_model=Success[MessageResponse])
async def delete_project(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await ProjectService(db).delete(user, project_id)
    await db.commit()
    return {"success": True, "data": {"message": "Project deleted."}}
