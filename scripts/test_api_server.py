import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""API服务器 V3 - 多平台 + 用户系统"""
import uvicorn
from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
from app.ai.llm_client import llm_client
from app.ai.title_scorer import title_scorer
from app.ai.title_pipeline import title_pipeline
from app.ai.user_manager import user_manager

app = FastAPI(title="AI电商标题优化 V3")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ===== User API =====
class RegisterRequest(BaseModel):
    phone: str = Field(..., description="手机号")
    password: str = Field(..., min_length=6, description="密码")

class LoginRequest(BaseModel):
    phone: str
    password: str

@app.post("/api/v1/user/register")
async def register(req: RegisterRequest):
    return user_manager.register(req.phone, req.password)

@app.post("/api/v1/user/login")
async def login(req: LoginRequest):
    return user_manager.login(req.phone, req.password)

@app.get("/api/v1/user/me")
async def get_me(authorization: str = Header(default="")):
    token = authorization.replace("Bearer ", "")
    if not token:
        return {"success": False, "error": "未登录"}
    verify = user_manager.verify_token(token)
    if not verify["valid"]:
        return {"success": False, "error": verify["error"]}
    usage = user_manager.get_usage(verify["user_id"])
    return {"success": True, "phone": verify["phone"], "usage": usage}

@app.get("/api/v1/user/usage")
async def get_usage(authorization: str = Header(default="")):
    token = authorization.replace("Bearer ", "")
    if not token:
        return {"used": 0, "limit": 3, "remaining": 3, "plan": "guest"}
    verify = user_manager.verify_token(token)
    if not verify["valid"]:
        return {"used": 0, "limit": 3, "remaining": 3, "plan": "guest"}
    return user_manager.get_usage(verify["user_id"])

# ===== Admin API =====
@app.get("/api/v1/admin/set-vip")
async def set_vip(phone: str, admin_key: str = ""):
    if admin_key != "aititles2026admin":
        return {"success": False, "error": "无权限"}
    return user_manager.set_vip(phone)

@app.get("/api/v1/admin/users")
async def list_users(admin_key: str = ""):
    if admin_key != "aititles2026admin":
        return {"success": False, "error": "无权限"}
    return user_manager.list_users()

# ===== Title API =====
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

@app.post("/api/v1/title/generate")
async def generate_titles(req: TitleGenerateRequest):
    result = await llm_client.generate_titles(req.product_info, req.platform, req.count)
    return {"titles": result, "platform": req.platform, "product_info": req.product_info}

@app.post("/api/v1/title/score")
async def score_title(req: TitleScoreRequest, authorization: str = Header(default="")):
    result = title_scorer.score(title=req.title, category=req.category, top_keywords=req.keywords, platform=req.platform)
    # 保存历史记录
    token = authorization.replace("Bearer ", "")
    if token:
        verify = user_manager.verify_token(token)
        if verify["valid"]:
            user_manager.save_history(verify["user_id"], "score", req.platform, req.title, result["total_score"], result["grade"])
    return {"title": req.title, "result": result}

@app.post("/api/v1/title/batch-score")
async def batch_score(titles: list[str], category: str = "", platform: str = "pinduoduo"):
    results = []
    for t in titles[:20]:
        score = title_scorer.score(title=t, category=category, platform=platform)
        results.append({"title": t, "total_score": score["total_score"], "grade": score["grade"]})
    results.sort(key=lambda x: -x["total_score"])
    return {"count": len(results), "results": results}

@app.post("/api/v1/title/optimize")
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
            import json as js
            for t in result["top_titles"][:3]:
                user_manager.save_history(verify2["user_id"], "generate", req.platform, t["title"], t["total_score"], t["grade"], req.product_info)
    return result

@app.get("/api/v1/user/history")
async def get_history(authorization: str = Header(default="")):
    token = authorization.replace("Bearer ", "")
    if not token:
        return {"success": False, "error": "未登录"}
    verify = user_manager.verify_token(token)
    if not verify["valid"]:
        return {"success": False, "error": verify["error"]}
    records = user_manager.get_history(verify["user_id"])
    return {"success": True, "records": records}

@app.get("/api/v1/admin/stats")
async def admin_stats(admin_key: str = ""):
    if admin_key != "aititles2026admin":
        return {"success": False, "error": "无权限"}
    import sqlite3
    from datetime import datetime
    conn = sqlite3.connect("data/users.db")
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT COUNT(*) FROM history WHERE action='score'")
    total_scores = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM history WHERE action='generate'")
    total_generates = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT user_id) FROM history WHERE created_at LIKE ?", (today+'%',))
    today_active = c.fetchone()[0]
    conn.close()
    return {"total_scores": total_scores, "total_generates": total_generates, "today_active": today_active}

@app.get("/api/v1/admin/recent-history")
async def admin_recent_history(admin_key: str = ""):
    if admin_key != "aititles2026admin":
        return {"success": False, "error": "无权限"}
    import sqlite3
    conn = sqlite3.connect("data/users.db")
    c = conn.cursor()
    c.execute("""SELECT h.user_id, h.action, h.platform, h.title, h.score, h.created_at, u.phone
                FROM history h LEFT JOIN users u ON h.user_id=u.id
                ORDER BY h.id DESC LIMIT 50""")
    records = []
    for row in c.fetchall():
        records.append({"user_id":row[0],"action":row[1],"platform":row[2],"title":row[3],"score":row[4],"created_at":row[5],"phone":row[6]})
    conn.close()
    return {"records": records}

@app.get("/api/v1/hot-keywords")
async def hot_keywords(platform: str = "pinduoduo", category: str = ""):
    """热搜词查询 - 免费引流工具"""
    import json as _json
    p_path = f"data/keywords_{platform}.json"
    import os
    if not os.path.exists(p_path):
        return {"success": False, "error": "暂无该平台数据"}
    
    with open(p_path, "r", encoding="utf-8") as f:
        keywords = _json.load(f)
    
    # 按品类过滤
    if category:
        keywords = [kw for kw in keywords if kw.get("category", "") == category]
    
    # 按类型分组
    result = {"品类词": [], "属性词": [], "修饰词": [], "营销词": []}
    for kw in keywords:
        word = kw.get("word", kw.get("keyword", ""))
        kw_type = kw.get("type", kw.get("word_type", "其他"))
        if kw_type in result:
            result[kw_type].append(word)
        elif kw_type == "功能词":
            result["属性词"].append(word)
    
    # 每类最多20个
    for k in result:
        result[k] = result[k][:20]
    
    platform_names = {"pinduoduo": "拼多多", "taobao": "淘宝/天猫", "douyin": "抖音", "xiaohongshu": "小红书"}
    categories_list = ["女装", "母婴", "家居日用", "零食", "美妆配饰"]
    
    total = sum(len(v) for v in result.values())
    return {
        "success": True,
        "platform": platform,
        "platform_name": platform_names.get(platform, platform),
        "category": category or "全部",
        "total": total,
        "keywords": result,
        "categories": categories_list,
    }

@app.get("/api/v1/platforms")
async def list_platforms():
    return {"platforms": [
        {"id": "pinduoduo", "name": "拼多多", "max_length": 60, "best_range": "20-35字"},
        {"id": "taobao", "name": "淘宝/天猫", "max_length": 30, "best_range": "20-28字"},
        {"id": "douyin", "name": "抖音", "max_length": 30, "best_range": "20-28字"},
        {"id": "xiaohongshu", "name": "小红书", "max_length": 30, "best_range": "20-28字"},
    ]}

@app.get("/")
async def root():
    return {"status": "ok", "version": "3.0", "message": "AI电商标题优化服务"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
