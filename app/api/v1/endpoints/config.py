"""公开配置 API — 前端初始化用（Sentry DSN 等）"""

import os

from fastapi import APIRouter

router = APIRouter()


@router.get("/public")
async def public_config():
    """返回前端初始化所需的公开配置"""
    return {
        "success": True,
        "sentry_dsn": os.environ.get("SENTRY_FRONTEND_DSN", ""),
        "version": "3.0",
    }
