"""标题优化Pipeline - 生成+评分+排序 完整链路"""

import json
import re
from app.ai.llm_client import llm_client
from app.ai.title_scorer import title_scorer


class TitlePipeline:
    """完整标题优化Pipeline：生成 → 评分 → 排序 → 输出"""

    async def run(self, product_info: str, platform: str = "pinduoduo",
                  category: str = "", count: int = 5, llm=None) -> dict:
        """
        执行完整Pipeline
        1. 解析商品信息
        2. AI生成多组候选标题
        3. 规则过滤（去掉不合格的）
        4. 逐条评分
        5. 排序输出Top N
        """
        # Step 1: AI生成候选标题（多生成一些，过滤后保留最好的）
        generate_count = count * 2  # 生成双倍数量，过滤后取最好的
        raw_titles = await self._generate_titles(product_info, platform, generate_count, llm=llm)

        if not raw_titles:
            return {"success": False, "error": "标题生成失败，请检查商品信息", "titles": []}

        # Step 2: 规则过滤（去掉明显不合格的）
        filtered_titles = self._filter_titles(raw_titles, platform)

        # Step 3: 逐条评分
        scored_titles = []
        for title_info in filtered_titles:
            title_text = title_info["title"]
            score_result = title_scorer.score(
                title_text, category, 
                product_info=product_info
            )
            scored_titles.append({
                "title": title_text,
                "keywords": title_info.get("keywords", []),
                "strategy": title_info.get("strategy", ""),
                "total_score": score_result["total_score"],
                "grade": score_result["grade"],
                "dimensions": score_result["dimensions"],
                "suggestions": score_result["suggestions"],
                "char_count": len(title_text),
            })

        # Step 4: 按总分排序，取Top N
        scored_titles.sort(key=lambda x: -x["total_score"])
        top_titles = scored_titles[:count]

        # Step 5: 生成总结建议
        summary = self._generate_summary(top_titles)

        return {
            "success": True,
            "product_info": product_info,
            "platform": platform,
            "category": category,
            "total_generated": len(raw_titles),
            "total_after_filter": len(filtered_titles),
            "top_titles": top_titles,
            "summary": summary,
        }

    async def _generate_titles(self, product_info: str, platform: str, count: int, llm=None) -> list:
        """调用LLM生成标题"""
        client = llm or llm_client
        try:
            result = await client.generate_titles(product_info, platform, count)

            # 解析JSON
            json_str = result
            if "```json" in result:
                json_str = result.split("```json")[1].split("```")[0]
            elif "```" in result:
                json_str = result.split("```")[1].split("```")[0]

            titles = json.loads(json_str.strip())

            # 确保格式统一
            formatted = []
            for t in titles:
                if isinstance(t, str):
                    formatted.append({"title": t, "keywords": [], "strategy": ""})
                elif isinstance(t, dict):
                    formatted.append({
                        "title": t.get("title", ""),
                        "keywords": t.get("keywords", []),
                        "strategy": t.get("strategy", ""),
                    })
            return [f for f in formatted if f["title"]]

        except json.JSONDecodeError:
            # JSON解析失败，尝试按行提取
            lines = result.strip().split("\n")
            titles = []
            for line in lines:
                line = line.strip().strip("-").strip("*").strip()
                if line and len(line) > 5 and len(line) < 60:
                    titles.append({"title": line, "keywords": [], "strategy": ""})
            return titles
        except Exception as e:
            print(f"标题生成出错：{e}")
            return []

    def _filter_titles(self, titles: list, platform: str) -> list:
        """规则过滤：去掉明显不合格的标题"""
        filtered = []
        max_len = 40 if platform == "pinduoduo" else 35

        # 禁用词列表
        forbidden = ["最好", "最低价", "第一", "顶级", "极品", "万能", "完美",
                     "搜索", "找到我们", "拼单", "刷单", "好评返现"]

        for t in titles:
            title = t["title"]

            # 过滤条件
            if len(title) < 10:
                continue
            if len(title) > max_len:
                # 超长的尝试截断而不是丢弃
                title = title[:max_len]
                t["title"] = title
            if any(fw in title for fw in forbidden):
                continue
            # 去重（降低阈值，保留更多候选）
            is_dup = False
            for existing in filtered:
                if self._similarity(title, existing["title"]) > 0.85:
                    is_dup = True
                    break
            if is_dup:
                continue

            filtered.append(t)

        return filtered

    def _similarity(self, a: str, b: str) -> float:
        """简单的字符重合率计算"""
        set_a = set(a)
        set_b = set(b)
        if not set_a or not set_b:
            return 0
        return len(set_a & set_b) / len(set_a | set_b)

    def _generate_summary(self, top_titles: list) -> dict:
        """生成总结建议"""
        if not top_titles:
            return {"recommendation": "未生成有效标题", "avg_score": 0}

        avg_score = sum(t["total_score"] for t in top_titles) / len(top_titles)
        best = top_titles[0]

        return {
            "recommendation": f"推荐使用第1条标题「{best['title']}」，评分{best['total_score']}分（{best['grade']}）",
            "avg_score": round(avg_score, 1),
            "best_title": best["title"],
            "best_score": best["total_score"],
        }


# 全局单例
title_pipeline = TitlePipeline()