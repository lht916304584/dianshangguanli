import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_user(client: AsyncClient):
    response = await client.post("/api/v1/users/", json={
        "email": "test@example.com",
        "password": "securepass123",
        "full_name": "Test User",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "id" in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    payload = {"email": "dup@example.com", "password": "pass1234"}
    await client.post("/api/v1/users/", json=payload)
    response = await client.post("/api/v1/users/", json=payload)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login(client: AsyncClient):
    await client.post("/api/v1/users/", json={
        "email": "login@example.com",
        "password": "pass1234",
    })
    response = await client.post("/api/v1/auth/login", json={
        "email": "login@example.com",
        "password": "pass1234",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post("/api/v1/users/", json={
        "email": "wrongpw@example.com",
        "password": "correct",
    })
    response = await client.post("/api/v1/auth/login", json={
        "email": "wrongpw@example.com",
        "password": "wrong",
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient):
    await client.post("/api/v1/users/", json={
        "email": "me@example.com",
        "password": "pass1234",
    })
    login = await client.post("/api/v1/auth/login", json={
        "email": "me@example.com",
        "password": "pass1234",
    })
    token = login.json()["access_token"]
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"
