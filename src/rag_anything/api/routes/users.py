"""User-facing and admin routes."""

from fastapi import APIRouter

from rag_anything.api.deps import AdminUser, CurrentUser
from rag_anything.db.models.user import User
from rag_anything.schemas.auth import UserOut

router = APIRouter()


@router.get("/me", tags=["users"], response_model=UserOut)
async def me(user: CurrentUser) -> User:
    return user


@router.get("/admin/ping", tags=["admin"])
async def admin_ping(user: AdminUser) -> dict[str, str]:
    return {"status": "ok", "role": user.role.value}
