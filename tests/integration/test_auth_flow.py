import httpx
import pytest

pytestmark = pytest.mark.integration

EMAIL = "walker@example.com"
PASSWORD = "a-sufficiently-long-password"


def signup_payload(email: str = EMAIL, username: str | None = None) -> dict[str, str]:
    """Username defaults to the email's local part so callers that only vary
    the email still get a unique username."""
    return {
        "email": email,
        "username": username or email.split("@")[0].replace(".", "-"),
        "first_name": "Ada",
        "last_name": "Lovelace",
        "password": PASSWORD,
    }


async def signup(client: httpx.AsyncClient, email: str = EMAIL) -> httpx.Response:
    return await client.post("/api/auth/signup", json=signup_payload(email))


async def login(client: httpx.AsyncClient, email: str = EMAIL) -> httpx.Response:
    return await client.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )


async def test_signup_creates_an_active_user(client: httpx.AsyncClient) -> None:
    response = await signup(client)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == EMAIL
    assert body["username"] == "walker"
    assert body["first_name"] == "Ada"
    assert body["last_name"] == "Lovelace"
    assert body["role"] == "user"
    assert body["status"] == "active"
    assert "password_hash" not in body
    assert "password" not in body


async def test_signup_rejects_a_duplicate_email(client: httpx.AsyncClient) -> None:
    await signup(client)
    assert (await signup(client)).status_code == 409


async def test_signup_is_case_insensitive_about_email(client: httpx.AsyncClient) -> None:
    await signup(client, email="Case@Example.com")
    assert (await signup(client, email="case@example.com")).status_code == 409


async def test_signup_rejects_a_short_password(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/auth/signup",
        json={**signup_payload("short@example.com"), "password": "short"},
    )
    assert response.status_code == 422


async def test_login_returns_a_token_pair(client: httpx.AsyncClient) -> None:
    await signup(client)
    response = await login(client)
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 900


async def test_login_rejects_a_wrong_password(client: httpx.AsyncClient) -> None:
    await signup(client)
    response = await client.post(
        "/api/auth/login", json={"email": EMAIL, "password": "wrong-but-long-enough"}
    )
    assert response.status_code == 401


async def test_login_does_not_reveal_whether_an_account_exists(
    client: httpx.AsyncClient,
) -> None:
    await signup(client)
    wrong_password = await client.post(
        "/api/auth/login", json={"email": EMAIL, "password": "wrong-but-long-enough"}
    )
    no_such_user = await client.post(
        "/api/auth/login",
        json={"email": "ghost@example.com", "password": "wrong-but-long-enough"},
    )
    assert wrong_password.status_code == no_such_user.status_code == 401
    assert wrong_password.json()["detail"] == no_such_user.json()["detail"]


async def test_refresh_rotates_the_token(client: httpx.AsyncClient) -> None:
    await signup(client)
    original = (await login(client)).json()["refresh_token"]
    response = await client.post("/api/auth/refresh", json={"refresh_token": original})
    assert response.status_code == 200
    assert response.json()["refresh_token"] != original


async def test_a_rotated_refresh_token_cannot_be_reused(client: httpx.AsyncClient) -> None:
    await signup(client)
    original = (await login(client)).json()["refresh_token"]
    await client.post("/api/auth/refresh", json={"refresh_token": original})
    replay = await client.post("/api/auth/refresh", json={"refresh_token": original})
    assert replay.status_code == 401


async def test_replay_kills_the_whole_token_family(client: httpx.AsyncClient) -> None:
    """The one that proves rotation is worth having."""
    await signup(client)
    stolen = (await login(client)).json()["refresh_token"]
    rotated = (
        await client.post("/api/auth/refresh", json={"refresh_token": stolen})
    ).json()["refresh_token"]
    await client.post("/api/auth/refresh", json={"refresh_token": stolen})
    response = await client.post("/api/auth/refresh", json={"refresh_token": rotated})
    assert response.status_code == 401


async def test_refresh_rejects_an_unknown_token(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/auth/refresh", json={"refresh_token": "not-a-real-token"}
    )
    assert response.status_code == 401


async def test_logout_revokes_the_refresh_token(client: httpx.AsyncClient) -> None:
    await signup(client)
    token = (await login(client)).json()["refresh_token"]
    assert (await client.post("/api/auth/logout", json={"refresh_token": token})).status_code == 204
    response = await client.post("/api/auth/refresh", json={"refresh_token": token})
    assert response.status_code == 401


async def test_logout_is_idempotent(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/auth/logout", json={"refresh_token": "never-existed"}
    )
    assert response.status_code == 204