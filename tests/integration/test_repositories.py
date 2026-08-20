import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from rag_anything.db.models.user import UserRole, UserStatus
from rag_anything.db.repositories.refresh_tokens import RefreshTokenRepository
from rag_anything.db.repositories.users import UserRepository

pytestmark = pytest.mark.integration

FAKE_HASH = "$argon2id$fake"


async def test_create_user_defaults_to_active_user_role(session) -> None:
    user = await UserRepository(session).create(
        email="a@example.com", username="alice", first_name="Alice", last_name="Smith",
        password_hash=FAKE_HASH,
    )
    assert user.role is UserRole.user
    assert user.status is UserStatus.active
    assert user.created_at is not None


async def test_email_is_normalised_on_create_and_lookup(session) -> None:
    repo = UserRepository(session)
    await repo.create(
        email="  MixedCase@Example.COM ", username="  MixedCase ",
        first_name="  Mixed ", last_name=" Case ", password_hash=FAKE_HASH,
    )
    found = await repo.get_by_email("mixedcase@example.com")
    assert found is not None
    assert found.email == "mixedcase@example.com"
    assert found.username == "mixedcase"   # lowercased, like email
    assert found.first_name == "Mixed"     # stripped but case preserved
    assert found.last_name == "Case"


async def test_duplicate_email_is_rejected_by_the_database(session) -> None:
    repo = UserRepository(session)
    await repo.create(
        email="dup@example.com", username="dup1", first_name="D", last_name="P",
        password_hash=FAKE_HASH,
    )
    with pytest.raises(IntegrityError):
        await repo.create(
            email="DUP@example.com", username="dup2", first_name="D", last_name="P",
            password_hash=FAKE_HASH,
        )


async def test_get_by_email_returns_none_when_absent(session) -> None:
    assert await UserRepository(session).get_by_email("nobody@example.com") is None


async def test_get_by_id_round_trips(session) -> None:
    repo = UserRepository(session)
    created = await repo.create(
        email="id@example.com", username="ident", first_name="I", last_name="D",
        password_hash=FAKE_HASH,
    )
    assert await repo.get_by_id(created.id) is not None


async def test_refresh_token_round_trips(session) -> None:
    user = await UserRepository(session).create(
        email="rt@example.com", username="rt", first_name="R", last_name="T",
        password_hash=FAKE_HASH,
    )
    repo = RefreshTokenRepository(session)
    token = await repo.create(
        user_id=user.id,
        token_hash="a" * 64,
        family_id=uuid.uuid4(),
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    assert token.is_revoked is False
    assert await repo.get_by_hash("a" * 64) is not None


async def test_revoke_marks_a_single_token(session) -> None:
    user = await UserRepository(session).create(
        email="rev@example.com", username="rev", first_name="R", last_name="V",
        password_hash=FAKE_HASH,
    )
    repo = RefreshTokenRepository(session)
    token = await repo.create(
        user_id=user.id,
        token_hash="b" * 64,
        family_id=uuid.uuid4(),
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    await repo.revoke(token)
    revoked = await repo.get_by_hash("b" * 64)
    assert revoked is not None and revoked.is_revoked is True


async def test_revoke_family_revokes_every_live_token_in_the_chain(session) -> None:
    user = await UserRepository(session).create(
        email="fam@example.com", username="fam", first_name="F", last_name="M",
        password_hash=FAKE_HASH,
    )
    repo = RefreshTokenRepository(session)
    family_id = uuid.uuid4()
    expires = datetime.now(UTC) + timedelta(days=30)
    for char in "cde":
        await repo.create(
            user_id=user.id, token_hash=char * 64, family_id=family_id,
            expires_at=expires,
        )
    other = await repo.create(
        user_id=user.id, token_hash="f" * 64, family_id=uuid.uuid4(),
        expires_at=expires,
    )

    count = await repo.revoke_family(family_id)

    assert count == 3
    for char in "cde":
        token = await repo.get_by_hash(char * 64)
        assert token is not None and token.is_revoked is True
    survivor = await repo.get_by_hash(other.token_hash)
    assert survivor is not None and survivor.is_revoked is False


async def test_delete_expired_removes_only_expired_tokens(session) -> None:
    user = await UserRepository(session).create(
        email="exp@example.com", username="exp", first_name="E", last_name="X",
        password_hash=FAKE_HASH,
    )
    repo = RefreshTokenRepository(session)
    await repo.create(
        user_id=user.id, token_hash="1" * 64, family_id=uuid.uuid4(),
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    await repo.create(
        user_id=user.id, token_hash="2" * 64, family_id=uuid.uuid4(),
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )

    deleted = await repo.delete_expired()

    assert deleted == 1
    assert await repo.get_by_hash("1" * 64) is None
    assert await repo.get_by_hash("2" * 64) is not None