import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from rag_anything.api.deps import SessionDep
from rag_anything.db.models.user import User, UserStatus
from rag_anything.db.repositories.refresh_tokens import RefreshTokenRepository
from rag_anything.db.repositories.users import UserRepository
from rag_anything.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    SignupRequest,
    TokenPair,
    UserOut,
)
from rag_anything.security.passwords import hash_password, needs_rehash, verify_password
from rag_anything.security.tokens import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    refresh_expiry,
)
from rag_anything.settings import Settings

router = APIRouter(prefix="/auth", tags=["auth"])
log = structlog.get_logger(__name__)

INVALID_CREDENTIALS = "Incorrect email or password."
INVALID_REFRESH = "Invalid or expired refresh token."


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


async def _issue_token_pair(
    *, user: User, family_id: uuid.UUID, session: AsyncSession, settings: Settings
) -> TokenPair:
    """Mint an access token plus a fresh refresh token in the given family."""
    access_token = create_access_token(
        user_id=user.id,
        role=user.role,
        secret=settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
        ttl_minutes=settings.access_token_ttl_minutes,
    )
    refresh_token = generate_refresh_token()
    await RefreshTokenRepository(session).create(
        user_id=user.id,
        token_hash=hash_refresh_token(refresh_token),
        family_id=family_id,
        expires_at=refresh_expiry(settings.refresh_token_ttl_days),
    )
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_ttl_minutes * 60,
    )


@router.post("/signup", status_code=status.HTTP_201_CREATED, response_model=UserOut)
async def signup(payload: SignupRequest, session: SessionDep) -> User:
    users = UserRepository(session)
    try:
        user = await users.create(
            email=payload.email,
            username=payload.username,
            first_name=payload.first_name,
            last_name=payload.last_name,
            password_hash=hash_password(payload.password),
        )
    except IntegrityError as exc:
        await session.rollback()
        constraint = getattr(getattr(exc.orig, "__cause__", None), "constraint_name", "")
        detail = (
            "That username is already taken."
            if constraint == "ix_users_username"
            else "An account with that email already exists."
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from None
    log.info("auth.signup", user_id=str(user.id))
    return user


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, session: SessionDep, request: Request) -> TokenPair:
    settings = _settings(request)
    users = UserRepository(session)
    user = await users.get_by_email(payload.email)

    if user is None:
        hash_password(payload.password)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS
        )

    if not verify_password(payload.password, user.password_hash):
        log.info("auth.login_failed", user_id=str(user.id))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS
        )

    if user.status is UserStatus.suspended:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This account is suspended."
        )

    if needs_rehash(user.password_hash):
        await users.update_password_hash(user, hash_password(payload.password))

    log.info("auth.login", user_id=str(user.id))
    return await _issue_token_pair(
        user=user, family_id=uuid.uuid4(), session=session, settings=settings
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    payload: RefreshRequest, session: SessionDep, request: Request
) -> TokenPair:
    settings = _settings(request)
    tokens = RefreshTokenRepository(session)
    stored = await tokens.get_by_hash(hash_refresh_token(payload.refresh_token))

    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_REFRESH
        )

    if stored.is_revoked:
        revoked = await tokens.revoke_family(stored.family_id)
        await session.commit()
        log.warning(
            "auth.refresh_replay_detected",
            user_id=str(stored.user_id),
            family_id=str(stored.family_id),
            revoked=revoked,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_REFRESH
        )

    if stored.expires_at <= datetime.now(UTC):
        await tokens.revoke(stored)
        await session.commit()  
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_REFRESH
        )

    user = await UserRepository(session).get_by_id(stored.user_id)
    if user is None or user.status is UserStatus.suspended:
        await tokens.revoke_family(stored.family_id)
        await session.commit()  
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_REFRESH
        )

    await tokens.revoke(stored)
    return await _issue_token_pair(
        user=user, family_id=stored.family_id, session=session, settings=settings
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: RefreshRequest, session: SessionDep) -> Response:
    """Idempotent: an unknown or already-revoked token still returns 204."""
    tokens = RefreshTokenRepository(session)
    stored = await tokens.get_by_hash(hash_refresh_token(payload.refresh_token))
    if stored is not None and not stored.is_revoked:
        await tokens.revoke(stored)
        log.info("auth.logout", user_id=str(stored.user_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)