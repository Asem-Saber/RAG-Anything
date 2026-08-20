from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from rag_anything.db.models.user import User, UserRole, UserStatus
from rag_anything.db.repositories.users import UserRepository
from rag_anything.db.session import get_sessionmaker
from rag_anything.security.tokens import TokenError, decode_access_token
from rag_anything.settings import Settings


async def get_session() -> AsyncIterator[AsyncSession]:
    """One transaction per request: commit on success, roll back on any exception."""
    async with get_sessionmaker()() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


SessionDep = Annotated[AsyncSession, Depends(get_session)]

_bearer = HTTPBearer(auto_error=False, description="JWT access token")

async def get_current_user(
    request: Request,
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    """Resolve the caller from a bearer access token."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized

    settings: Settings = request.app.state.settings
    try:
        claims = decode_access_token(
            credentials.credentials,
            secret=settings.jwt_secret.get_secret_value(),
            algorithm=settings.jwt_algorithm,
        )
    except TokenError:
        raise unauthorized from None

    user = await UserRepository(session).get_by_id(claims.sub)
    if user is None:
        raise unauthorized
    if user.status is UserStatus.suspended:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This account is suspended."
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(user: CurrentUser) -> User:
    """Gate a route behind the admin role."""
    if user.role is not UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required."
        )
    return user


AdminUser = Annotated[User, Depends(require_admin)]