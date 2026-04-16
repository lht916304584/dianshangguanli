from fastapi import APIRouter

from app.api.v1.endpoints import health, auth, users, files, websocket, title

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(websocket.router, tags=["websocket"])
api_router.include_router(title.router, prefix="/title", tags=["标题优化"])
