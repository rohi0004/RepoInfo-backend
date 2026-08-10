"""Seeds essential rows: default roles/permissions, plans, and (optionally) a
demo super-admin user. Idempotent — safe to re-run."""

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.security import hash_password
from app.database.session import db_session_ctx
from app.models.billing import Plan
from app.models.enums import BillingPeriodEnum, GlobalRoleEnum, UserPlanEnum
from app.models.rbac import Permission, Role, RolePermission
from app.models.user import User, UserSettings

DEFAULT_ROLES = [
    ("super_admin", "Super Admin", "Full platform control."),
    ("admin", "Admin", "Platform administrator."),
    ("member", "Member", "Standard authenticated user."),
    ("viewer", "Viewer", "Read-only access."),
]

DEFAULT_PERMISSIONS = [
    ("repository:read", "repository", "read", "Read repositories."),
    ("repository:create", "repository", "create", "Add repositories."),
    ("repository:delete", "repository", "delete", "Delete repositories."),
    ("billing:manage", "billing", "manage", "Manage billing."),
    ("admin:read", "admin", "read", "Access admin dashboards."),
    ("chat:write", "chat", "write", "Send chat messages."),
]

DEFAULT_PLANS = [
    {
        "code": UserPlanEnum.FREE,
        "name": "Free",
        "price": 0,
        "billing_period": BillingPeriodEnum.MONTHLY,
        "description": "Start exploring your repositories with AI.",
        "features": [
            {"label": "3 repositories", "included": True},
            {"label": "500 AI messages / month", "included": True},
            {"label": "Public repos only", "included": True},
        ],
        "cta_label": "Get started",
        "sort_order": 1,
    },
    {
        "code": UserPlanEnum.PRO,
        "name": "Pro",
        "price": 19,
        "billing_period": BillingPeriodEnum.MONTHLY,
        "description": "For serious builders and small teams.",
        "features": [
            {"label": "Unlimited repositories", "included": True},
            {"label": "10,000 AI messages / month", "included": True},
            {"label": "Private repos", "included": True},
            {"label": "Security scanning", "included": True},
        ],
        "highlighted": True,
        "cta_label": "Upgrade to Pro",
        "sort_order": 2,
    },
    {
        "code": UserPlanEnum.TEAM,
        "name": "Team",
        "price": 49,
        "billing_period": BillingPeriodEnum.MONTHLY,
        "description": "Collaborate across projects.",
        "features": [
            {"label": "Everything in Pro", "included": True},
            {"label": "Team workspaces", "included": True},
            {"label": "Shared prompt library", "included": True},
        ],
        "cta_label": "Start Team plan",
        "sort_order": 3,
    },
]


async def seed_roles_and_permissions() -> None:
    async with db_session_ctx() as db:
        roles: dict[str, Role] = {}
        for code, name, desc in DEFAULT_ROLES:
            existing = (
                await db.execute(select(Role).where(Role.name == name))
            ).scalar_one_or_none()
            if existing:
                roles[code] = existing
                continue
            r = Role(name=name, description=desc, is_system=True)
            db.add(r)
            await db.flush()
            roles[code] = r

        perms: dict[str, Permission] = {}
        for code, resource, action, desc in DEFAULT_PERMISSIONS:
            existing = (
                await db.execute(select(Permission).where(Permission.code == code))
            ).scalar_one_or_none()
            if existing:
                perms[code] = existing
                continue
            p = Permission(code=code, resource=resource, action=action, description=desc)
            db.add(p)
            await db.flush()
            perms[code] = p

        for role_code, perm_codes in {
            "super_admin": list(perms.keys()),
            "admin": ["repository:read", "admin:read", "chat:write"],
            "member": ["repository:read", "repository:create", "chat:write"],
            "viewer": ["repository:read"],
        }.items():
            for pc in perm_codes:
                existing = (
                    await db.execute(
                        select(RolePermission).where(
                            RolePermission.role_id == roles[role_code].id,
                            RolePermission.permission_id == perms[pc].id,
                        )
                    )
                ).scalar_one_or_none()
                if existing:
                    continue
                db.add(RolePermission(role_id=roles[role_code].id, permission_id=perms[pc].id))


async def seed_plans() -> None:
    async with db_session_ctx() as db:
        for spec in DEFAULT_PLANS:
            existing = (
                await db.execute(select(Plan).where(Plan.code == spec["code"]))
            ).scalar_one_or_none()
            if existing:
                continue
            db.add(Plan(**spec))


async def seed_admin_user() -> None:
    async with db_session_ctx() as db:
        existing = (
            await db.execute(select(User).where(User.email == "admin@repoinfo.dev"))
        ).scalar_one_or_none()
        if existing:
            return
        user = User(
            email="admin@repoinfo.dev",
            username="admin",
            display_name="RepoInfo Admin",
            hashed_password=hash_password("ChangeMe!123"),
            email_verified=True,
            global_role=GlobalRoleEnum.SUPER_ADMIN,
            last_login_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        user.settings = UserSettings()
        db.add(user)


async def main() -> None:
    await seed_roles_and_permissions()
    await seed_plans()
    await seed_admin_user()
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
