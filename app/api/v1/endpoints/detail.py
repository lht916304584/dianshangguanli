"""详情图AI策划 API"""

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from app.ai.detail_planner import detail_planner
from app.ai.user_manager import user_manager

router = APIRouter()


class DetailPlanRequest(BaseModel):
    product_info: str = Field(..., min_length=2, max_length=500, description="商品信息")
    platform: str = Field(default="pinduoduo")
    category: str = Field(default="")


@router.post("/plan")
async def create_detail_plan(req: DetailPlanRequest, authorization: str = Header(default="")):
    token = authorization.replace("Bearer ", "")
    if not token:
        return {"success": False, "error": "请先登录"}

    verify = user_manager.verify_token(token)
    if not verify["valid"]:
        return {"success": False, "error": verify["error"]}

    credit = user_manager.use_credit(verify["user_id"])
    if not credit["success"]:
        return {"success": False, "error": credit["error"], "usage": credit["usage"]}

    try:
        result = await detail_planner.run(req.product_info, req.platform, req.category)
        user_manager.save_history(
            verify["user_id"], "detail_plan", req.platform,
            result.get("page_structure", [{}])[0].get("title", "") if result.get("page_structure") else "",
            0, "", req.product_info,
        )
        return result
    except Exception as e:
        return {"success": False, "error": f"策划生成失败：{str(e)}"}
