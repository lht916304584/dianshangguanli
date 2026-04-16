"""平台与热搜词 API"""

import json
import os

from fastapi import APIRouter

router = APIRouter()

PLATFORM_NAMES = {
    "pinduoduo": "拼多多",
    "taobao": "淘宝/天猫",
    "douyin": "抖音",
    "xiaohongshu": "小红书",
}

CATEGORIES = ["女装", "母婴", "家居日用", "零食", "美妆配饰"]


@router.get("/hot-keywords")
async def hot_keywords(platform: str = "pinduoduo", category: str = ""):
    """热搜词查询 - 免费引流工具"""
    p_path = f"data/keywords_{platform}.json"
    if not os.path.exists(p_path):
        return {"success": False, "error": "暂无该平台数据"}

    with open(p_path, "r", encoding="utf-8") as f:
        keywords = json.load(f)

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

    total = sum(len(v) for v in result.values())
    return {
        "success": True,
        "platform": platform,
        "platform_name": PLATFORM_NAMES.get(platform, platform),
        "category": category or "全部",
        "total": total,
        "keywords": result,
        "categories": CATEGORIES,
    }


@router.get("/platforms")
async def list_platforms():
    return {"platforms": [
        {"id": "pinduoduo", "name": "拼多多", "max_length": 60, "best_range": "20-35字"},
        {"id": "taobao", "name": "淘宝/天猫", "max_length": 30, "best_range": "20-28字"},
        {"id": "douyin", "name": "抖音", "max_length": 30, "best_range": "20-28字"},
        {"id": "xiaohongshu", "name": "小红书", "max_length": 30, "best_range": "20-28字"},
    ]}
