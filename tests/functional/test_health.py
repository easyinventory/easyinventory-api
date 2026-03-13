import pytest


@pytest.mark.asyncio
async def test_health_returns_200(client):
    response = await client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_response_body(client):
    response = await client.get("/health")
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "easyinventory-api"


@pytest.mark.asyncio
async def test_health_response_content_type(client):
    response = await client.get("/health")
    assert response.headers["content-type"] == "application/json"
