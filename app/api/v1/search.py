"""/search endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.base import Success
from app.schemas.search import SearchQuery, SearchResponse
from app.services.search_service import SearchService

router = APIRouter()


@router.post("", response_model=Success[SearchResponse])
async def search(
    payload: SearchQuery,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    resp = await SearchService(db).search(user, payload)
    return {"success": True, "data": resp.model_dump(by_alias=True)}
