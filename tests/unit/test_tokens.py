import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from rag_anything.db.models.user import UserRole
from rag_anything.security.tokens import (
    ExpiredTokenError,
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_refresh_token,
    refresh_expiry,
)

SECRET = "test-secret-do-not-use-in-production"
ALGORITHM = "HS256"

def test_access_token_round_trips() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(
        user_id=user_id,
        role=UserRole.admin,
        secret=SECRET,
        algorithm=ALGORITHM,
        ttl_minutes=15,
    )
    claims = decode_access_token(token, secret=SECRET, algorithm=ALGORITHM)
    assert claims.sub == user_id
    assert claims.role is UserRole.admin


def test_access_token_expiry_honours_the_ttl() -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    token = create_access_token(
        user_id=uuid.uuid4(),
        role=UserRole.user,
        secret=SECRET,
        algorithm=ALGORITHM,
        ttl_minutes=15,
        now=now,
    )
    claims = decode_access_token(token, secret=SECRET, algorithm=ALGORITHM)
    assert claims.issued_at == now
    assert claims.expires_at == now + timedelta(minutes=15)


def test_expired_access_token_is_rejected() -> None:
    token = create_access_token(
        user_id=uuid.uuid4(),
        role=UserRole.user,
        secret=SECRET,
        algorithm=ALGORITHM,
        ttl_minutes=15,
        now=datetime.now(UTC) - timedelta(hours=2),
    )
    with pytest.raises(ExpiredTokenError):
        decode_access_token(token, secret=SECRET, algorithm=ALGORITHM)


def test_token_signed_with_another_secret_is_rejected() -> None:
    token = create_access_token(
        user_id=uuid.uuid4(),
        role=UserRole.user,
        secret="attacker-secret",
        algorithm=ALGORITHM,
        ttl_minutes=15,
    )
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, secret=SECRET, algorithm=ALGORITHM)


def test_garbage_is_rejected() -> None:
    with pytest.raises(InvalidTokenError):
        decode_access_token("not.a.jwt", secret=SECRET, algorithm=ALGORITHM)


def test_unsigned_alg_none_token_is_rejected() -> None:
    """The classic JWT forgery: claim alg=none and supply no signature."""
    forged = jwt.encode(
        {"sub": str(uuid.uuid4()), "role": "admin", "typ": "access"},
        key="",
        algorithm="none",
    )
    with pytest.raises(InvalidTokenError):
        decode_access_token(forged, secret=SECRET, algorithm=ALGORITHM)


def test_each_access_token_has_a_unique_jti() -> None:
    kwargs = {
        "user_id": uuid.uuid4(),
        "role": UserRole.user,
        "secret": SECRET,
        "algorithm": ALGORITHM,
        "ttl_minutes": 15,
    }
    first = decode_access_token(
        create_access_token(**kwargs), secret=SECRET, algorithm=ALGORITHM
    )
    second = decode_access_token(
        create_access_token(**kwargs), secret=SECRET, algorithm=ALGORITHM
    )
    assert first.jti != second.jti


def test_refresh_tokens_are_unique_and_high_entropy() -> None:
    tokens = {generate_refresh_token() for _ in range(100)}
    assert len(tokens) == 100
    assert all(len(token) >= 43 for token in tokens)


def test_refresh_hash_is_deterministic_and_hides_the_token() -> None:
    token = generate_refresh_token()
    digest = hash_refresh_token(token)
    assert digest == hash_refresh_token(token)
    assert len(digest) == 64
    assert token not in digest


def test_different_refresh_tokens_hash_differently() -> None:
    assert hash_refresh_token(generate_refresh_token()) != hash_refresh_token(
        generate_refresh_token()
    )


def test_refresh_expiry_honours_the_ttl() -> None:
    now = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
    assert refresh_expiry(30, now=now) == now + timedelta(days=30)