import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rag_anything.db.models.user import User, UserRole


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def normalise_email(email: str | None) -> str | None:
        return email.strip().lower() if email is not None else None

    @staticmethod
    def normalise_username(username: str | None) -> str | None:
        """Same treatment as email: usernames are identifiers, so they compare
        case-insensitively. Normalising on write *and* on read is what makes the
        unique index actually prevent "Asem" and "asem" being two accounts."""
        return username.strip().lower() if username is not None else None

    async def create(
        self,
        *,
        email: str | None = None,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        password_hash: str | None = None,
        role: UserRole = UserRole.user,
    ) -> User:
        user = User(
            email=self.normalise_email(email),
            username=self.normalise_username(username),
            # Names are display data, not identifiers — strip padding but keep case.
            first_name=first_name.strip() if first_name is not None else None,
            last_name=last_name.strip() if last_name is not None else None,
            password_hash=password_hash,
            role=role,
        )
        self._session.add(user)
        await self._session.flush()
        return user

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str | None) -> User | None:
        # A None lookup would compile to "email IS NULL" and match an arbitrary
        # passwordless/OAuth account, so refuse it rather than return a stranger.
        normalised = self.normalise_email(email)
        if normalised is None:
            return None
        stmt = select(User).where(User.email == normalised)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_username(self, username: str | None) -> User | None:
        normalised = self.normalise_username(username)
        if normalised is None:
            return None
        stmt = select(User).where(User.username == normalised)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def update_password_hash(self, user: User, password_hash: str) -> None:
        user.password_hash = password_hash
        await self._session.flush()