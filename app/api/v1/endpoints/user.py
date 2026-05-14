"""用户相关 API — 注册/登录/用量/历史"""

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.ai.user_manager import user_manager

router = APIRouter()
_limiter = Limiter(key_func=get_remote_address)


class RegisterRequest(BaseModel):
    phone: str = Field(..., description="手机号")
    password: str = Field(..., min_length=6, description="密码")


class LoginRequest(BaseModel):
    phone: str
    password: str


class ResetPasswordRequest(BaseModel):
    phone: str = Field(..., description="手机号")
    password: str = Field(..., min_length=6, description="新密码")
    confirm_password: str = Field(..., min_length=6, description="确认密码")


@router.post("/register")
@_limiter.limit("5/minute")
async def register(request: Request, req: RegisterRequest):
    return user_manager.register(req.phone, req.password)


@router.post("/login")
@_limiter.limit("10/minute")
async def login(request: Request, req: LoginRequest):
    return user_manager.login(req.phone, req.password)


@router.post("/reset-password")
@_limiter.limit("3/minute")
async def reset_password(request: Request, req: ResetPasswordRequest):
    if req.password != req.confirm_password:
        return {"success": False, "error": "两次密码不一致"}
    return user_manager.reset_password(req.phone, req.password)


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
