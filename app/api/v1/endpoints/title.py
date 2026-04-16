"""标题优化 API"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.ai.llm_client import llm_client

router = APIRouter()


class TitleRequest(BaseModel):
    product_info: str = Field(..., min_length=2, max_length=500, description="商品信息")
    platform: str = Field(default="pinduoduo", description="平台：pinduoduo/taobao/douyin/xiaohongshu")
    count: int = Field(default=5, ge=1, le=10, description="生成数量")


class TitleResponse(BaseModel):
    titles: str
    platform: str
    product_info: str


@router.post("/generate", response_model=TitleResponse)
async def generate_titles(req: TitleRequest):
    """AI 生成优化标题"""
    try:
        result = await llm_client.generate_titles(
            product_info=req.product_info,
            platform=req.platform,
            count=req.count,
        )
        return TitleResponse(
            titles=result,
            platform=req.platform,
            product_info=req.product_info,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"标题生成失败：{str(e)}")


@router.get("/health")
async def health():
    return {"status": "ok", "module": "title-engine"}