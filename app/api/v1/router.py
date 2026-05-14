from fastapi import APIRouter

from app.api.v1.endpoints import admin, detail, health, image, platform, title, user

api_router = APIRouter()

# 用户系统（注册/登录/用量/历史）
api_router.include_router(user.router, prefix="/user", tags=["用户"])
# 标题优化（生成/评分/优化）
api_router.include_router(title.router, prefix="/title", tags=["标题优化"])
# 管理员（VIP/用户列表/统计）
api_router.include_router(admin.router, prefix="/admin", tags=["管理员"])
# 详情图AI策划
api_router.include_router(detail.router, prefix="/detail", tags=["详情图策划"])
# AI生图
api_router.include_router(image.router, prefix="/image", tags=["AI生图"])
# 平台与热搜词
api_router.include_router(platform.router, tags=["平台"])
# 健康检查
api_router.include_router(health.router, tags=["health"])
