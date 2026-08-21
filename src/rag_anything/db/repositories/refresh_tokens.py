import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from rag_anything.db.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        token_hash: str,
        family_id: uuid.UUID,
        expires_at: datetime,
    ) -> RefreshToken:
        token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            family_id=family_id,
            expires_at=expires_at,
        )
        self._session.add(token)
        await self._session.flush()
        return token

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def revoke(self, token: RefreshToken, *, now: datetime | None = None) -> None:
        token.revoked_at = now or datetime.now(UTC)
        await self._session.flush()

    async def revoke_family(
        self, family_id: uuid.UUID, *, now: datetime | None = None
    ) -> int:
        stmt = (
            update(RefreshToken)
            .where(
                RefreshToken.family_id == family_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now or datetime.now(UTC))
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return int(result.rowcount or 0)

    async def delete_expired(self, *, now: datetime | None = None) -> int:
        stmt = delete(RefreshToken).where(
            RefreshToken.expires_at < (now or datetime.now(UTC))
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return int(result.rowcount or 0)