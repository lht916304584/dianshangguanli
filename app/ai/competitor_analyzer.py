"""竞品标题分析器 — AI分析对手关键词策略、卖点和反制建议"""

import json
from app.ai.llm_client import llm_client
from app.ai.title_scorer import title_scorer

PLATFORM_NAMES = {
    "pinduoduo": "拼多多",
    "taobao": "淘宝/天猫",
    "douyin": "抖音",
    "xiaohongshu": "小红书",
}

SYSTEM_PROMPT = """你是资深电商竞品分析专家，精通各平台的搜索算法和标题优化策略。
你需要分析用户提供的竞品标题，提取关键词策略和卖点，给出差异化建议。
必须严格按JSON格式输出，不要输出任何其他内容。"""


class CompetitorAnalyzer:
    async def analyze(
        self,
        titles: list[str],
        platform: str = "pinduoduo",
        category: str = "",
        llm=None,
    ) -> dict:
        # 1. Score each title for reference
        scored = []
        for t in titles:
            s = title_scorer.score(title=t, category=category, platform=platform)
            scored.append({"title": t, "score": s["total_score"], "grade": s["grade"]})

        # 2. LLM analysis
        pname = PLATFORM_NAMES.get(platform, "拼多多")
        titles_text = "\n".join(f"{i+1}. {t}" for i, t in enumerate(titles))

        user_prompt = f"""请分析以下{pname}竞品标题（品类：{category or '自动识别'}）：

{titles_text}

请严格按以下JSON格式输出分析结果：
{{
  "keyword_analysis": [
    {{"word": "关键词", "count": 出现次数, "type": "品类词/属性词/修饰词/营销词"}}
  ],
  "title_structure": [
    {{"title": "原标题", "pattern": "结构描述，如：品牌+品类+属性+修饰", "keywords": ["拆解出的关键词"]}}
  ],
  "selling_points": [
    {{"point": "卖点", "count": 出现次数, "type": "效果卖点/材质卖点/风格卖点/场景卖点/价格卖点"}}
  ],
  "strategy_summary": "竞品整体策略总结（2-3句话）",
  "counter_suggestions": [
    "建议1：具体可执行的差异化建议",
    "建议2：...",
    "建议3：..."
  ],
  "recommended_keywords": ["建议添加的关键词1", "关键词2"]
}}

要求：
- keyword_analysis 按count降序，至少提取8个关键词
- title_structure 为每个标题都做结构拆解
- selling_points 至少3个
- counter_suggestions 至少3条可执行建议
- 只输出JSON，不要任何解释"""

        try:
            client = llm or llm_client
            raw = await client.chat(
                prompt=user_prompt,
                system_prompt=SYSTEM_PROMPT,
                temperature=0.5,
                max_tokens=3000,
            )
            analysis = self._parse_json(raw)
        except Exception as e:
            analysis = {
                "keyword_analysis": [],
                "title_structure": [],
                "selling_points": [],
                "strategy_summary": f"AI分析失败：{e}",
                "counter_suggestions": [],
                "recommended_keywords": [],
            }

        return {
            "success": True,
            "platform": platform,
            "category": category,
            "titles_count": len(titles),
            "scored_titles": scored,
            "analysis": analysis,
        }

    def _parse_json(self, raw: str) -> dict:
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())


competitor_analyzer = CompetitorAnalyzer()
