"""LLM 文案配置 API — 用户自管 API Key 模式"""

import httpx
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.ai.llm_client import LLMClient
from app.ai.user_manager import user_manager

router = APIRouter()


class LLMConfigRequest(BaseModel):
    api_key: str = Field(default="", max_length=500)
    base_url: str = Field(default="https://api.deepseek.com", max_length=500)
    model: str = Field(default="deepseek-chat", max_length=100)


def _get_verified_user(authorization: str):
    token = authorization.replace("Bearer ", "").strip()
    if not token:
        return None
    verify = user_manager.verify_token(token)
    return verify if verify["valid"] else None


@router.get("/config")
async def get_llm_config(authorization: str = Header(default="")):
    """获取当前用户的LLM配置（API Key已脱敏）。"""
    verify = _get_verified_user(authorization)
    if not verify:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录",
        )
    config = user_manager.get_llm_config(verify["user_id"])
    return {"success": True, "config": config}


@router.post("/config")
async def save_llm_config(
    req: LLMConfigRequest,
    authorization: str = Header(default=""),
):
    """保存/更新LLM配置。api_key为空表示不修改已有key。"""
    verify = _get_verified_user(authorization)
    if not verify:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录",
        )
    result = user_manager.save_llm_config(
        verify["user_id"],
        api_key=req.api_key,
        base_url=req.base_url,
        model=req.model,
    )
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "保存失败"),
        )
    return {"success": True, "msg": "配置已保存"}


@router.get("/test")
async def test_llm_api(authorization: str = Header(default="")):
    """测试LLM API连通性（不消耗额度）。"""
    verify = _get_verified_user(authorization)
    if not verify:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录",
        )

    config = user_manager.get_raw_llm_config(verify["user_id"])
    if not config or not config.get("api_key"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先配置LLM API Key",
        )

    base_url = config.get("base_url", "https://api.deepseek.com").rstrip("/")
    api_key = config["api_key"]
    model = config.get("model", "deepseek-chat")
    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1. 先尝试 /v1/models（OpenAI标准端点）
            resp = await client.get(f"{base_url}/models", headers=headers)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    models = data.get("data", [])
                    model_found = any(m.get("id") == model for m in models)
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
                        "message": f"API 返回非 JSON 数据: {resp.text[:200]}",
                    }

            # 2. /models 不存在，fallback 测试 chat completions（发一个极短请求验证端点存在）
            if resp.status_code == 404:
                resp2 = await client.post(
                    f"{base_url}/chat/completions",
                    headers={**headers, "Content-Type": "application/json"},
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": "hi"}],
                        "max_tokens": 1,
                    },
                )
                if resp2.status_code == 404:
                    return {
                        "success": False,
                        "status": "error",
                        "message": "API 端点不存在（/models 和 /chat/completions 均返回 404），请检查 Base URL 是否正确",
                    }

                # 400/422 表示端点存在但参数被拒，说明连通正常
                if resp2.status_code in (400, 422):
                    return {
                        "success": True,
                        "status": "connected",
                        "model_found": None,
                        "model": model,
                        "message": "API 端点连通正常（models 列表不可用，但 chat 端点可用）",
                    }

                if resp2.status_code == 401:
                    try:
                        err = resp2.json().get("error", {})
                        msg = err.get("message", "API Key 无效")
                    except Exception:
                        msg = resp2.text[:200]
                    return {
                        "success": False,
                        "status": "error",
                        "message": f"API Key 无效: {msg}",
                    }

                try:
                    err = resp2.json().get("error", {})
                    msg = err.get("message", f"HTTP {resp2.status_code}")
                except Exception:
                    msg = resp2.text[:200]
                return {
                    "success": False,
                    "status": "error",
                    "message": msg,
                }

            # /models 返回了非 200 非 404 的状态
            try:
                err = resp.json().get("error", {})
                msg = err.get("message", f"HTTP {resp.status_code}")
            except Exception:
                msg = resp.text[:200]
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
