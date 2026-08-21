import httpx
import pytest

from rag_anything.db.models.user import UserRole, UserStatus
from rag_anything.db.repositories.users import UserRepository
from tests.integration.test_auth_flow import signup_payload

pytestmark = pytest.mark.integration

EMAIL = "protected@example.com"
PASSWORD = "a-sufficiently-long-password"


async def signup_and_login(client: httpx.AsyncClient, email: str = EMAIL) -> str:
    await client.post("/api/auth/signup", json=signup_payload(email))
    response = await client.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    return str(response.json()["access_token"])


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_me_requires_a_token(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/me")).status_code == 401


async def test_me_rejects_a_garbage_token(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/me", headers=bearer("not.a.jwt"))
    assert response.status_code == 401


async def test_me_rejects_a_non_bearer_scheme(client: httpx.AsyncClient) -> None:
    token = await signup_and_login(client)
    response = await client.get("/api/me", headers={"Authorization": f"Basic {token}"})
    assert response.status_code == 401


async def test_me_returns_the_authenticated_user(client: httpx.AsyncClient) -> None:
    token = await signup_and_login(client)
    response = await client.get("/api/me", headers=bearer(token))
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == EMAIL
    assert body["role"] == "user"
    assert "password_hash" not in body


async def test_a_refresh_token_is_not_accepted_as_an_access_token(
    client: httpx.AsyncClient,
) -> None:
    """The `typ` claim check is what makes this fail."""
    await client.post("/api/auth/signup", json=signup_payload(EMAIL))
    login = await client.post(
        "/api/auth/login", json={"email": EMAIL, "password": PASSWORD}
    )
    response = await client.get(
        "/api/me", headers=bearer(login.json()["refresh_token"])
    )
    assert response.status_code == 401


async def test_suspended_user_is_rejected_immediately(client, session) -> None:
    token = await signup_and_login(client)
    user = await UserRepository(session).get_by_email(EMAIL)
    assert user is not None
    user.status = UserStatus.suspended
    await session.flush()

    response = await client.get("/api/me", headers=bearer(token))
    assert response.status_code == 403


async def test_admin_route_rejects_a_regular_user(client: httpx.AsyncClient) -> None:
    token = await signup_and_login(client)
    response = await client.get("/api/admin/ping", headers=bearer(token))
    assert response.status_code == 403


async def test_admin_route_accepts_an_admin(client, session) -> None:
    await client.post("/api/auth/signup", json=signup_payload("boss@example.com"))
    user = await UserRepository(session).get_by_email("boss@example.com")
    assert user is not None
    user.role = UserRole.admin
    await session.flush()

    login = await client.post(
        "/api/auth/login", json={"email": "boss@example.com", "password": PASSWORD}
    )
    response = await client.get(
        "/api/admin/ping", headers=bearer(login.json()["access_token"])
    )
    assert response.status_code == 200
