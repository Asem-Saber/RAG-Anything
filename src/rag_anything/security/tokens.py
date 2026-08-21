import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from rag_anything.db.models.user import UserRole

_REFRESH_TOKEN_BYTES = 32


class TokenError(Exception):
    """Base class for token failures."""


class InvalidTokenError(TokenError):
    """Signature, structure, or claims are wrong."""


class ExpiredTokenError(TokenError):
    """Well-formed, but past its expiry."""


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    sub: uuid.UUID
    role: UserRole
    jti: str
    issued_at: datetime
    expires_at: datetime


def create_access_token(
    *,
    user_id: uuid.UUID,
    role: UserRole,
    secret: str,
    algorithm: str,
    ttl_minutes: int,
    now: datetime | None = None,
) -> str:
    """Mint a short-lived signed access token."""
    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=ttl_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role.value,
        "typ": "access",
        "jti": secrets.token_urlsafe(16),
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_access_token(token: str, *, secret: str, algorithm: str) -> AccessTokenClaims:
    """Verify and parse an access token."""
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[algorithm],
            options={"require": ["exp", "iat", "sub", "jti"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise ExpiredTokenError("access token has expired") from exc
    except jwt.PyJWTError as exc:
        raise InvalidTokenError("access token is invalid") from exc

    if payload.get("typ") != "access":
        raise InvalidTokenError("not an access token")

    try:
        subject = uuid.UUID(payload["sub"])
        role = UserRole(payload["role"])
    except (KeyError, ValueError) as exc:
        raise InvalidTokenError("access token claims are malformed") from exc

    return AccessTokenClaims(
        sub=subject,
        role=role,
        jti=payload["jti"],
        issued_at=datetime.fromtimestamp(payload["iat"], tz=UTC),
        expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
    )


def generate_refresh_token() -> str:
    """A 256-bit opaque token. Returned to the client once and never stored raw."""
    return secrets.token_urlsafe(_REFRESH_TOKEN_BYTES)


def hash_refresh_token(token: str) -> str:
    """SHA-256 hex digest — deterministic, so the row is findable by indexed lookup."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_expiry(ttl_days: int, now: datetime | None = None) -> datetime:
    return (now or datetime.now(UTC)) + timedelta(days=ttl_days)