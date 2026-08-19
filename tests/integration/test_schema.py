import pytest
from sqlalchemy import inspect

pytestmark = pytest.mark.integration


async def test_expected_tables_exist(engine) -> None:
    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda sync: inspect(sync).get_table_names())
    assert "users" in tables
    assert "refresh_tokens" in tables


async def test_user_email_is_uniquely_indexed(engine) -> None:
    async with engine.connect() as conn:
        indexes = await conn.run_sync(lambda sync: inspect(sync).get_indexes("users"))
    email = [ix for ix in indexes if ix["column_names"] == ["email"]]
    assert email and email[0]["unique"] is True


async def test_refresh_token_hash_is_uniquely_indexed(engine) -> None:
    async with engine.connect() as conn:
        indexes = await conn.run_sync(
            lambda sync: inspect(sync).get_indexes("refresh_tokens")
        )
    token_hash = [ix for ix in indexes if ix["column_names"] == ["token_hash"]]
    assert token_hash and token_hash[0]["unique"] is True