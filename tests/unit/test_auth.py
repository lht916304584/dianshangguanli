import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_register(client: AsyncClient):
    resp = await client.post("/api/v1/user/register", json={
        "phone": "13800138001",
        "password": "test123456",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "token" in data
    assert data["phone"] == "13800138001"


@pytest.mark.asyncio
async def test_register_duplicate_phone(client: AsyncClient):
    payload = {"phone": "13800138002", "password": "test123456"}
    await client.post("/api/v1/user/register", json=payload)
    resp = await client.post("/api/v1/user/register", json=payload)
    assert resp.json()["success"] is False


@pytest.mark.asyncio
async def test_register_invalid_phone(client: AsyncClient):
    resp = await client.post("/api/v1/user/register", json={
        "phone": "123",
        "password": "test123456",
    })
    assert resp.json()["success"] is False


@pytest.mark.asyncio
async def test_login(client: AsyncClient):
    await client.post("/api/v1/user/register", json={
        "phone": "13800138003",
        "password": "test123456",
    })
    resp = await client.post("/api/v1/user/login", json={
        "phone": "13800138003",
        "password": "test123456",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post("/api/v1/user/register", json={
        "phone": "13800138004",
        "password": "correct123",
    })
    resp = await client.post("/api/v1/user/login", json={
        "phone": "13800138004",
        "password": "wrongpassword",
    })
    assert resp.json()["success"] is False


@pytest.mark.asyncio
async def test_get_me(auth_client):
    client, token = auth_client
    resp = await client.get("/api/v1/user/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "phone" in data


@pytest.mark.asyncio
async def test_usage(auth_client):
    client, _ = auth_client
    resp = await client.get("/api/v1/user/usage")
    assert resp.status_code == 200
    data = resp.json()
    assert "used" in data
    assert "limit" in data
    assert "remaining" in data


@pytest.mark.asyncio
async def test_score_free(client: AsyncClient):
    resp = await client.post("/api/v1/title/score", json={
        "title": "法式碎花方领短袖连衣裙女夏季新款收腰显瘦",
        "platform": "pinduoduo",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "result" in data
    assert "total_score" in data["result"]


@pytest.mark.asyncio
async def test_reset_password(client: AsyncClient):
    await client.post("/api/v1/user/register", json={
        "phone": "13800138005",
        "password": "oldpass123",
    })
    resp = await client.post("/api/v1/user/reset-password", json={
        "phone": "13800138005",
        "password": "newpass123",
        "confirm_password": "newpass123",
    })
    assert resp.json()["success"] is True

    login = await client.post("/api/v1/user/login", json={
        "phone": "13800138005",
        "password": "newpass123",
    })
    assert login.json()["success"] is True
