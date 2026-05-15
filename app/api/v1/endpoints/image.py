"""AI 生图 API — 用户自管 API Key 模式"""

import httpx
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.ai.image_engine import image_engine
from app.ai.user_manager import user_manager

router = APIRouter()


class ImageConfigRequest(BaseModel):
    api_key: str = Field(default="", max_length=500)
    base_url: str = Field(default="https://api.openai.com/v1", max_length=500)
    model: str = Field(default="dall-e-3", max_length=100)
    size: str = Field(default="1024x1024", max_length=50)


class ImageGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=2, max_length=1000)
    image_type: str = Field(default="main")
    count: int = Field(default=1, ge=1, le=4)


def _get_verified_user(authorization: str):
    token = authorization.replace("Bearer ", "").strip()
    if not token:
        return None
    verify = user_manager.verify_token(token)
    return verify if verify["valid"] else None


@router.get("/config")
async def get_image_config(authorization: str = Header(default="")):
    """获取当前用户的生图配置（API Key 已脱敏）。"""
    verify = _get_verified_user(authorization)
    if not verify:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录",
        )
    config = user_manager.get_image_config(verify["user_id"])
    return {"success": True, "config": config}


@router.post("/config")
async def save_image_config(
    req: ImageConfigRequest,
    authorization: str = Header(default=""),
):
    """保存/更新生图配置。api_key 为空表示不修改已有 key。"""
    verify = _get_verified_user(authorization)
    if not verify:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录",
        )
    result = user_manager.save_image_config(
        verify["user_id"],
        api_key=req.api_key,
        base_url=req.base_url,
        model=req.model,
        size=req.size,
    )
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "保存失败"),
        )
    return {"success": True, "msg": "配置已保存"}


@router.post("/generate")
async def generate_image(
    req: ImageGenerateRequest,
    authorization: str = Header(default=""),
):
    """生成图片（需要登录并消耗 1 次 AI 额度）。"""
    verify = _get_verified_user(authorization)
    if not verify:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录后再使用生图功能",
        )

    # 读取用户配置
    raw_key = user_manager._get_raw_image_api_key(verify["user_id"])
    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先配置生图 API Key",
        )

    config_dict = user_manager.get_image_config(verify["user_id"])
    config_dict["api_key"] = raw_key

    # 消耗额度
    credit = user_manager.use_credit(verify["user_id"])
    if not credit["success"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=credit["error"],
        )

    # 调用生图引擎
    result = await image_engine.generate(
        prompt=req.prompt,
        config=config_dict,
        image_type=req.image_type,
        count=req.count,
    )

    if result["status"] == "error":
        # 额度已扣除但生成失败，仍然返回错误
        return {
            "success": False,
            "error": result["error"],
            "prompt": result["prompt"],
        }

    # 保存历史
    user_manager.save_history(
        verify["user_id"],
        action="image_generate",
        platform="",
        title=req.prompt[:100],
        result_json=",".join(result["urls"]),
    )

    return {
        "success": True,
        "urls": result["urls"],
        "prompt": result["prompt"],
        "image_type": req.image_type,
        "count": len(result["urls"]),
    }


@router.get("/test")
async def test_image_api(authorization: str = Header(default="")):
    """测试生图 API 连通性（不消耗额度）。"""
    verify = _get_verified_user(authorization)
    if not verify:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录",
        )

    raw_key = user_manager._get_raw_image_api_key(verify["user_id"])
    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先配置生图 API Key",
        )

    config_dict = user_manager.get_image_config(verify["user_id"])
    base_url = config_dict.get("base_url", "https://api.openai.com/v1").rstrip("/")
    model = config_dict.get("model", "dall-e-3")

    test_url = f"{base_url}/models"
    headers = {
        "Authorization": f"Bearer {raw_key}",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(test_url, headers=headers)
            raw_text = resp.text
            if resp.status_code == 200:
                # 尝试解析，确认返回的是 JSON
                try:
                    data = resp.json()
                    models = data.get("data", [])
                    # 检查目标模型是否在列表中
                    model_found = any(
                        m.get("id") == model for m in models
                    )
                    return {
                        "success": True,
                        "status": "connected",
                        "model_found": model_found,
                        "model": model,
                        "message": "API 连通正常" + (
                            "" if model_found else "，但目标模型未在列表中找到，请确认模型名称"
                        ),
                    }
                except Exception:
                    return {
                        "success": False,
                        "status": "error",
                        "message": f"API 返回非 JSON 数据: {raw_text[:200]}",
                    }
            else:
                try:
                    data = resp.json()
                    err = data.get("error", {})
                    msg = err.get("message", f"HTTP {resp.status_code}")
                except Exception:
                    msg = f"HTTP {resp.status_code}: {raw_text[:200]}"
                return {
                    "success": False,
                    "status": "error",
                    "message": msg,
                }
    except httpx.TimeoutException:
        return {
            "success": False,
            "status": "timeout",
            "message": "连接超时，请检查网络或 Base URL",
        }
    except Exception as e:
        return {
            "success": False,
            "status": "error",
            "message": f"请求异常: {str(e)}",
        }
