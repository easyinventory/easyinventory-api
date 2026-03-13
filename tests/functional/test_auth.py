import pytest


async def test_me_returns_401_without_token(client):
    response = await client.get("/api/me")
    assert response.status_code == 401


async def test_me_returns_401_with_invalid_token(client):
    response = await client.get(
        "/api/me",
        headers={"Authorization": "Bearer garbage.token.here"},
    )
    assert response.status_code == 401


async def test_me_returns_401_detail_message(client):
    response = await client.get("/api/me")
    data = response.json()
    assert "detail" in data


async def test_me_returns_www_authenticate_header(client):
    response = await client.get("/api/me")
    assert response.headers.get("www-authenticate") == "Bearer"
