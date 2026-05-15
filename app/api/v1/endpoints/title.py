"""标题优化 API — 生成/评分/批量评分/优化Pipeline（已安全加固）"""

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.ai.llm_client import LLMClient, llm_client
from app.ai.title_scorer import title_scorer
from app.ai.title_pipeline import title_pipeline
from app.ai.competitor_analyzer import competitor_analyzer
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


class BatchScoreRequest(BaseModel):
    titles: list[str] = Field(..., max_length=50)
    category: str = Field(default="")
    platform: str = Field(default="pinduoduo")


class BatchOptimizeRequest(BaseModel):
    items: list[dict] = Field(..., max_length=20)
    platform: str = Field(default="pinduoduo")


class CompetitorAnalyzeRequest(BaseModel):
    titles: list[str] = Field(..., min_length=1, max_length=10)
    platform: str = Field(default="pinduoduo")
    category: str = Field(default="")


def _get_verified_user(authorization: str):
    """从 Authorization Header 中解析并校验用户，失败则返回 None。"""
    token = authorization.replace("Bearer ", "").strip()
    if not token:
        return None
    verify = user_manager.verify_token(token)
    return verify if verify["valid"] else None


@router.post("/generate")
async def generate_titles(
    req: TitleGenerateRequest,
    authorization: str = Header(default=""),
):
    """生成标题（需要登录并消耗次数）。"""
    verify = _get_verified_user(authorization)
    if not verify:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录后再使用标题生成功能",
        )

    credit = user_manager.use_credit(verify["user_id"])
    if not credit["success"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=credit["error"],
        )

    config = user_manager.get_raw_llm_config(verify["user_id"])
    if not config or not config.get("api_key"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先配置AI文案API Key",
        )
    client = LLMClient(api_key=config["api_key"], base_url=config["base_url"], model=config["model"])
    result = await client.generate_titles(req.product_info, req.platform, req.count)
    return {"titles": result, "platform": req.platform, "product_info": req.product_info}


@router.post("/score")
async def score_title(
    req: TitleScoreRequest,
    authorization: str = Header(default=""),
):
    """评分单个标题（登录后自动保存历史）。"""
    result = title_scorer.score(
        title=req.title,
        category=req.category,
        top_keywords=req.keywords,
        platform=req.platform,
    )
    # 已登录则保存历史记录
    verify = _get_verified_user(authorization)
    if verify:
        user_manager.save_history(
            verify["user_id"], "score", req.platform,
            req.title, result["total_score"], result["grade"],
        )
    return {"title": req.title, "result": result}


@router.post("/batch-score")
async def batch_score(
    req: BatchScoreRequest,
    authorization: str = Header(default=""),
):
    """批量评分（需要登录）。"""
    verify = _get_verified_user(authorization)
    if not verify:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录后再使用批量评分功能",
        )

    results = []
    for t in req.titles[:50]:
        score = title_scorer.score(title=t, category=req.category, platform=req.platform)
        results.append({"title": t, "total_score": score["total_score"], "grade": score["grade"]})
    results.sort(key=lambda x: -x["total_score"])
    return {"count": len(results), "results": results, "platform": req.platform}


@router.post("/batch-optimize")
async def batch_optimize(
    req: BatchOptimizeRequest,
    authorization: str = Header(default=""),
):
    """批量AI优化（需要登录，每条消耗1次额度）。"""
    verify = _get_verified_user(authorization)
    if not verify:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录后再使用批量优化功能",
        )

    usage = user_manager.get_usage(verify["user_id"])
    max_count = min(len(req.items), 20, usage["remaining"])
    if max_count <= 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="今日次数已用完",
        )

    config = user_manager.get_raw_llm_config(verify["user_id"])
    if not config or not config.get("api_key"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先配置AI文案API Key",
        )
    client = LLMClient(api_key=config["api_key"], base_url=config["base_url"], model=config["model"])

    results = []
    for item in req.items[:max_count]:
        credit = user_manager.use_credit(verify["user_id"])
        if not credit["success"]:
            break
        try:
            r = await title_pipeline.run(
                product_info=item.get("product_info", ""),
                platform=req.platform,
                category=item.get("category", ""),
                count=1,
                llm=client,
            )
            if r.get("success") and r.get("top_titles"):
                best = r["top_titles"][0]
                results.append({
                    "product_info": item.get("product_info", ""),
                    "title": best["title"],
                    "total_score": best["total_score"],
                    "grade": best["grade"],
                })
            else:
                results.append({
                    "product_info": item.get("product_info", ""),
                    "title": "",
                    "total_score": 0,
                    "grade": "",
                    "error": r.get("error", "生成失败"),
                })
        except Exception as e:
            results.append({
                "product_info": item.get("product_info", ""),
                "title": "",
                "total_score": 0,
                "grade": "",
                "error": str(e),
            })

    return {"count": len(results), "results": results, "platform": req.platform}


@router.post("/optimize")
async def optimize_title(
    req: PipelineRequest,
    authorization: str = Header(default=""),
):
    """AI 优化标题 Pipeline（需要登录并消耗次数）。"""
    verify = _get_verified_user(authorization)
    if not verify:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录后再使用AI优化功能",
        )

    credit = user_manager.use_credit(verify["user_id"])
    if not credit["success"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=credit["error"],
        )

    config = user_manager.get_raw_llm_config(verify["user_id"])
    if not config or not config.get("api_key"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先配置AI文案API Key",
        )
    client = LLMClient(api_key=config["api_key"], base_url=config["base_url"], model=config["model"])
    result = await title_pipeline.run(
        product_info=req.product_info,
        platform=req.platform,
        category=req.category,
        count=req.count,
        llm=client,
    )

    # 保存历史记录
    if result.get("success") and result.get("top_titles"):
        for t in result["top_titles"][:3]:
            user_manager.save_history(
                verify["user_id"], "generate", req.platform,
                t["title"], t["total_score"], t["grade"], req.product_info,
            )

    return result


@router.post("/competitor-analyze")
async def competitor_analyze(
    req: CompetitorAnalyzeRequest,
    authorization: str = Header(default=""),
):
    """竞品标题AI分析（需要登录并消耗次数）。"""
    verify = _get_verified_user(authorization)
    if not verify:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录后再使用竞品分析功能",
        )

    credit = user_manager.use_credit(verify["user_id"])
    if not credit["success"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=credit["error"],
        )

    config = user_manager.get_raw_llm_config(verify["user_id"])
    if not config or not config.get("api_key"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先配置AI文案API Key",
        )
    client = LLMClient(api_key=config["api_key"], base_url=config["base_url"], model=config["model"])

    cleaned = [t.strip() for t in req.titles if t.strip()]
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请输入至少一个竞品标题",
        )

    result = await competitor_analyzer.analyze(
        titles=cleaned[:10],
        platform=req.platform,
        category=req.category,
        llm=client,
    )

    summary = result.get("analysis", {}).get("strategy_summary", "")
    user_manager.save_history(
        verify["user_id"], "competitor", req.platform,
        f"竞品分析({len(cleaned)}条)", 0, "", summary,
    )

    return result
