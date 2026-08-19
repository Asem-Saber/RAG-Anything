import httpx
import pytest

from rag_anything.main import create_app


@pytest.fixture
def bare_client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=create_app())
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_liveness_returns_ok(bare_client: httpx.AsyncClient) -> None:
    async with bare_client as client:
        response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_response_carries_a_generated_request_id(
    bare_client: httpx.AsyncClient,
) -> None:
    async with bare_client as client:
        response = await client.get("/api/health")
    assert response.headers["X-Request-ID"]


async def test_inbound_request_id_is_echoed(bare_client: httpx.AsyncClient) -> None:
    async with bare_client as client:
        response = await client.get(
            "/api/health", headers={"X-Request-ID": "abc-123"}
        )
    assert response.headers["X-Request-ID"] == "abc-123"


async def test_each_request_gets_a_distinct_id(bare_client: httpx.AsyncClient) -> None:
    async with bare_client as client:
        first = await client.get("/api/health")
        second = await client.get("/api/health")
    assert first.headers["X-Request-ID"] != second.headers["X-Request-ID"]