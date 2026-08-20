from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from rag_anything.api.deps import get_session
from rag_anything.db.base import Base
from rag_anything.db.models import *
from rag_anything.main import create_app
from rag_anything.settings import Settings, get_settings

TEST_DATABASE_URL = get_settings().test_database_url


@pytest.fixture(scope="session")
async def engine() -> AsyncIterator[object]:
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(engine) -> AsyncIterator[AsyncSession]:
    connection = await engine.connect()
    transaction = await connection.begin()
    maker = async_sessionmaker(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    async with maker() as session:
        yield session
    await transaction.rollback()
    await connection.close()


@pytest.fixture
def test_settings() -> Settings:
    """Settings for the app under test.

    ``database_url`` is a computed property, so it cannot be passed in — point
    ``postgres_db`` at the test database instead and the DSN follows. In
    practice the app never opens a connection during tests anyway: the ``client``
    fixture below overrides ``get_session`` with the test's own session.
    """
    base = get_settings()
    return Settings(
        _env_file=None,
        environment="test",
        log_level="WARNING",
        postgres_host=base.postgres_host,
        postgres_port=base.postgres_port,
        postgres_user=base.postgres_user,
        postgres_password=base.postgres_password.get_secret_value(),
        postgres_db=base.postgres_test_db,
        jwt_secret="test-secret-not-for-production",
    )


@pytest.fixture
async def client(
    test_settings: Settings, session: AsyncSession
) -> AsyncIterator[httpx.AsyncClient]:
    """An HTTP client whose requests share the test's rolled-back session.

    Overriding ``get_session`` is what keeps tests isolated: everything a request
    writes lands inside the outer transaction that the ``session`` fixture rolls
    back on teardown, so no test can see another test's users.
    """
    app = create_app(test_settings)

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = override_get_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()