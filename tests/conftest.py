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


# Disable rate limiting in tests
@pytest.fixture(autouse=True)
def disable_rate_limits(monkeypatch):
    """Monkeypatch slowapi limiter to be a no-op during tests."""
    from app.api.v1.endpoints import user

    original_limit = user._limiter.limit

    def no_op_limit(*args, **kwargs):
        def decorator(f):
            return f
        return decorator

    monkeypatch.setattr(user._limiter, "limit", no_op_limit)
