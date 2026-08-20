"""Create an admin account.

Usage:
    uv run python scripts/seed_admin.py --email admin@example.com --username admin
"""

import argparse
import asyncio
import getpass
import os
import sys

from sqlalchemy.exc import IntegrityError

from rag_anything.db.models.user import UserRole
from rag_anything.db.repositories.users import UserRepository
from rag_anything.db.session import dispose_engine, get_sessionmaker
from rag_anything.security.passwords import hash_password

MIN_PASSWORD_LENGTH = 12


async def seed_admin(
    email: str, username: str, first_name: str, last_name: str, password: str
) -> int:
    async with get_sessionmaker()() as session:
        users = UserRepository(session)
        existing = await users.get_by_email(email)
        if existing is not None:
            if existing.role is UserRole.admin:
                print(f"{existing.email} is already an admin.")
                return 0
            existing.role = UserRole.admin
            await session.commit()
            print(f"Promoted {existing.email} to admin.")
            return 0

        taken = await users.get_by_username(username)
        if taken is not None:
            print(
                f"Username {username!r} already belongs to {taken.email}. "
                "Pick another with --username.",
                file=sys.stderr,
            )
            return 1

        try:
            user = await users.create(
                email=email,
                username=username,
                first_name=first_name,
                last_name=last_name,
                password_hash=hash_password(password),
                role=UserRole.admin,
            )
            await session.commit()
        except IntegrityError:
            await session.rollback()
            print(f"Could not create {email}: it clashes with an existing account.", file=sys.stderr)
            return 1

        print(f"Created admin {user.email} ({user.id}).")
        return 0


async def _run(
    email: str, username: str, first_name: str, last_name: str, password: str
) -> int:
    """Dispose inside the same loop that opened the connections."""
    try:
        return await seed_admin(email, username, first_name, last_name, password)
    finally:
        await dispose_engine()


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an admin user.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--first-name", default="Site")
    parser.add_argument("--last-name", default="Admin")
    args = parser.parse_args()

    password = os.getenv("ADMIN_PASSWORD") or getpass.getpass("Admin password: ")
    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.", file=sys.stderr)
        return 1

    return asyncio.run(
        _run(args.email, args.username, args.first_name, args.last_name, password)
    )


if __name__ == "__main__":
    raise SystemExit(main())
