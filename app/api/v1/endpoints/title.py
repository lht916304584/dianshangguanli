"""标题优化 API — 生成/评分/批量评分/优化Pipeline"""

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from app.ai.llm_client import llm_client
from app.ai.title_scorer import title_scorer
from app.ai.title_pipeline import title_pipeline
from app.ai.user_manager import user_manager

router = APIRouter()


class TitleGenerateRequest(BaseModel):
    product_info: str = Field(..., min_length=2, max_length=500)
    platform: str = Field(default="pinduoduo")
    count: int = Field(default=5, ge=1, le=10)


class TitleScoreRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    category: str = Field(default="")
    platform: str = Field(default="pinduoduo")
    keywords: list = Field(default=None)


class PipelineRequest(BaseModel):
    product_info: str = Field(..., min_length=2, max_length=500)
    platform: str = Field(default="pinduoduo")
    category: str = Field(default="")
    count: int = Field(default=5, ge=1, le=10)


@router.post("/generate")
async def generate_titles(req: TitleGenerateRequest):
    result = await llm_client.generate_titles(req.product_info, req.platform, req.count)
    return {"titles": result, "platform": req.platform, "product_info": req.product_info}


@router.post("/score")
async def score_title(req: TitleScoreRequest, authorization: str = Header(default="")):
    result = title_scorer.score(
        title=req.title, category=req.category,
        top_keywords=req.keywords, platform=req.platform,
    )
    # 保存历史记录
    token = authorization.replace("Bearer ", "")
    if token:
        verify = user_manager.verify_token(token)
        if verify["valid"]:
            user_manager.save_history(
                verify["user_id"], "score", req.platform,
                req.title, result["total_score"], result["grade"],
            )
    return {"title": req.title, "result": result}


@router.post("/batch-score")
async def batch_score(titles: list[str], category: str = "", platform: str = "pinduoduo"):
    results = []
    for t in titles[:20]:
        score = title_scorer.score(title=t, category=category, platform=platform)
        results.append({"title": t, "total_score": score["total_score"], "grade": score["grade"]})
    results.sort(key=lambda x: -x["total_score"])
    return {"count": len(results), "results": results}


@router.post("/optimize")
async def optimize_title(req: PipelineRequest, authorization: str = Header(default="")):
    # Check user credit
    token = authorization.replace("Bearer ", "")
    if token:
        verify = user_manager.verify_token(token)
        if verify["valid"]:
            credit = user_manager.use_credit(verify["user_id"])
            if not credit["success"]:
                return {"success": False, "error": credit["error"], "usage": credit["usage"]}

    result = await title_pipeline.run(
        product_info=req.product_info, platform=req.platform,
        category=req.category, count=req.count,
    )
    # 保存历史记录
    token2 = authorization.replace("Bearer ", "")
    if token2 and result.get("success") and result.get("top_titles"):
        verify2 = user_manager.verify_token(token2)
        if verify2["valid"]:
            for t in result["top_titles"][:3]:
                user_manager.save_history(
                    verify2["user_id"], "generate", req.platform,
                    t["title"], t["total_score"], t["grade"], req.product_info,
                )
    return result
