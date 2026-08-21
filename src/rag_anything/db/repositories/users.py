import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rag_anything.db.models.user import User, UserRole


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def normalise_email(email: str) -> str:
        return email.strip().lower()

    @staticmethod
    def normalise_username(username: str) -> str:
        return username.strip().lower()

    async def create(
        self,
        *,
        email: str,
        username: str,
        first_name: str,
        last_name: str,
        password_hash: str,
        role: UserRole = UserRole.user,
    ) -> User:
        user = User(
            email=self.normalise_email(email),
            username=self.normalise_username(username),
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            password_hash=password_hash,
            role=role,
        )
        self._session.add(user)
        await self._session.flush()
        return user

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == self.normalise_email(email))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == self.normalise_username(username))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def update_password_hash(self, user: User, password_hash: str) -> None:
        user.password_hash = password_hash
        await self._session.flush()