import pytest


async def test_health_returns_200(client):
    response = await client.get("/health")
    assert response.status_code == 200


async def test_health_response_body(client):
    response = await client.get("/health")
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "easyinventory-api"


async def test_health_response_content_type(client):
    response = await client.get("/health")
    assert response.headers["content-type"] == "application/json"


async def test_unknown_route_returns_404(client):
    response = await client.get("/nonexistent")
    assert response.status_code == 404


async def test_docs_endpoint_accessible(client):
    response = await client.get("/docs")
    assert response.status_code == 200
