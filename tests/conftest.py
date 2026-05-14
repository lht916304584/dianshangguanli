import os

os.environ["JWT_SECRET"] = os.environ.get("JWT_SECRET", "test-jwt-secret")
os.environ["ADMIN_KEY"] = os.environ.get("ADMIN_KEY", "test-admin-key")
os.environ["DEEPSEEK_API_KEY"] = os.environ.get("DEEPSEEK_API_KEY", "test-dummy")

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
