"""Delete refresh tokens that are past their expiry.

Usage:
    uv run python scripts/cleanup_tokens.py

Safe to run at any time and as often as you like: expiry is already enforced on
read, so this only reclaims rows that can no longer authenticate anything.
"""

import asyncio

from rag_anything.db.repositories.refresh_tokens import RefreshTokenRepository
from rag_anything.db.session import dispose_engine, get_sessionmaker


async def cleanup_tokens() -> int:
    async with get_sessionmaker()() as session:
        deleted = await RefreshTokenRepository(session).delete_expired()
        await session.commit()
        print(f"Deleted {deleted} expired refresh token(s).")
        return 0


async def _run() -> int:
    """Dispose inside the same loop that opened the connections."""
    try:
        return await cleanup_tokens()
    finally:
        await dispose_engine()


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
