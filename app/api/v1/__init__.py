"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    analytics,
    auth,
    billing,
    chat,
    notifications,
    profile,
    projects,
    repositories,
    search,
    settings as settings_router,
    uploads,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/user", tags=["users"])
api_router.include_router(profile.router, prefix="/profile", tags=["profile"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(repositories.router, prefix="/repositories", tags=["repositories"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(uploads.router, prefix="/uploads", tags=["uploads"])
api_router.include_router(settings_router.router, prefix="/settings", tags=["settings"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(billing.router, prefix="/billing", tags=["billing"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
