"""Generic base repository with common CRUD helpers.

Subclasses only need to declare `model = <SQLAlchemy class>` and can add
domain-specific methods on top.
"""

import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, id_: uuid.UUID) -> ModelT | None:
        return await self.db.get(self.model, id_)

    async def get_or_404(self, id_: uuid.UUID) -> ModelT:
        obj = await self.get(id_)
        if obj is None:
            raise NoResultFound(f"{self.model.__name__} {id_} not found")
        return obj

    async def create(self, **fields: Any) -> ModelT:
        obj = self.model(**fields)
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def update(self, obj: ModelT, **fields: Any) -> ModelT:
        for key, value in fields.items():
            if value is not None:
                setattr(obj, key, value)
        await self.db.flush()
        return obj

    async def delete(self, obj: ModelT) -> None:
        await self.db.delete(obj)
        await self.db.flush()

    async def soft_delete(self, obj: ModelT) -> None:
        from datetime import datetime, timezone
        setattr(obj, "deleted_at", datetime.now(timezone.utc))
        await self.db.flush()

    async def list(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        order_by: Any | None = None,
        filters: list[Any] | None = None,
    ) -> tuple[list[ModelT], int]:
        stmt = select(self.model)
        count_stmt = select(func.count()).select_from(self.model)
        if hasattr(self.model, "deleted_at"):
            stmt = stmt.where(self.model.deleted_at.is_(None))
            count_stmt = count_stmt.where(self.model.deleted_at.is_(None))
        for f in filters or []:
            stmt = stmt.where(f)
            count_stmt = count_stmt.where(f)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        stmt = stmt.offset(offset).limit(limit)
        rows = (await self.db.execute(stmt)).scalars().all()
        total = (await self.db.execute(count_stmt)).scalar_one()
        return list(rows), total
