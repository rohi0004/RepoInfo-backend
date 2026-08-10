"""Fine-grained, database-driven permission checks layered on top of global roles.

Global roles (`GlobalRoleEnum`) cover coarse platform admin checks cheaply via
`app.dependencies.auth.require_global_role`. This module checks feature-level
permission *codes* (e.g. "billing:manage", "repository:delete") assigned via
`Role` -> `Permission` -> `UserRole`, optionally scoped to an organization.
"""

import uuid

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError
from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.models.enums import GlobalRoleEnum
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.user import User


async def user_has_permission(
    db: AsyncSession, user: User, permission_code: str, organization_id: uuid.UUID | None = None
) -> bool:
    if user.global_role == GlobalRoleEnum.SUPER_ADMIN:
        return True

    stmt = (
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user.id, Permission.code == permission_code)
    )
    if organization_id is not None:
        stmt = stmt.where(UserRole.organization_id.in_([organization_id, None]))
    result = await db.execute(stmt.limit(1))
    return result.scalar_one_or_none() is not None


def require_permission(permission_code: str):
    async def _check(
        user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
    ) -> User:
        if not await user_has_permission(db, user, permission_code):
            raise ForbiddenError(f"Missing required permission: {permission_code}")
        return user

    return _check
