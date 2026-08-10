"""/notifications endpoints."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.pagination import PageParams, pagination_params
from app.models.user import User
from app.schemas.base import MessageResponse, PaginatedResponse, Success
from app.schemas.notification import NotificationOut
from app.services.notification_service import NotificationService

router = APIRouter()


@router.get("", response_model=Success[PaginatedResponse[NotificationOut]])
async def list_notifications(
    page: PageParams = Depends(pagination_params),
    unread_only: bool = Query(False, alias="unreadOnly"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    items, total = await NotificationService(db).list(
        user, unread_only=unread_only, offset=page.offset, limit=page.limit
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


@router.post("/{notif_id}/read", response_model=Success[NotificationOut])
async def mark_read(
    notif_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    out = await NotificationService(db).mark_read(user, notif_id)
    await db.commit()
    return {"success": True, "data": out.model_dump(by_alias=True)}


@router.post("/read-all", response_model=Success[MessageResponse])
async def mark_all_read(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    count = await NotificationService(db).mark_all_read(user)
    await db.commit()
    return {"success": True, "data": {"message": f"Marked {count} as read."}}
