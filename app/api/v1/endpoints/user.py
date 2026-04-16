"""用户相关 API — 注册/登录/用量/历史"""

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from app.ai.user_manager import user_manager

router = APIRouter()


class RegisterRequest(BaseModel):
    phone: str = Field(..., description="手机号")
    password: str = Field(..., min_length=6, description="密码")


class LoginRequest(BaseModel):
    phone: str
    password: str


@router.post("/register")
async def register(req: RegisterRequest):
    return user_manager.register(req.phone, req.password)


@router.post("/login")
async def login(req: LoginRequest):
    return user_manager.login(req.phone, req.password)


@router.get("/me")
async def get_me(authorization: str = Header(default="")):
    token = authorization.replace("Bearer ", "")
    if not token:
        return {"success": False, "error": "未登录"}
    verify = user_manager.verify_token(token)
    if not verify["valid"]:
        return {"success": False, "error": verify["error"]}
    usage = user_manager.get_usage(verify["user_id"])
    return {"success": True, "phone": verify["phone"], "usage": usage}


@router.get("/usage")
async def get_usage(authorization: str = Header(default="")):
    token = authorization.replace("Bearer ", "")
    if not token:
        return {"used": 0, "limit": 3, "remaining": 3, "plan": "guest"}
    verify = user_manager.verify_token(token)
    if not verify["valid"]:
        return {"used": 0, "limit": 3, "remaining": 3, "plan": "guest"}
    return user_manager.get_usage(verify["user_id"])


@router.get("/history")
async def get_history(authorization: str = Header(default="")):
    token = authorization.replace("Bearer ", "")
    if not token:
        return {"success": False, "error": "未登录"}
    verify = user_manager.verify_token(token)
    if not verify["valid"]:
        return {"success": False, "error": verify["error"]}
    records = user_manager.get_history(verify["user_id"])
    return {"success": True, "records": records}
