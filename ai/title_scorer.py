"""标题评分引擎 - 5维度规则评分"""

import re
import json
import os

# 加载关键词库
KEYWORD_DB = {}
db_path = "data/keyword_database.json"
if os.path.exists(db_path):
    with open(db_path, "r", encoding="utf-8") as f:
        kw_list = json.load(f)
    for kw in kw_list:
        KEYWORD_DB[kw["keyword"]] = kw

# 禁用词库
FORBIDDEN_WORDS = {
    "极限词": ["最好", "最低价", "最优", "最新款", "第一", "顶级", "极品", "最畅销", "最火",
              "独家", "仅此一家", "全网独卖", "无可比拟", "绝无仅有",
              "万能", "完美", "100%", "零缺点", "永久"],
    "虚假促销": ["仅限今天", "最后1件", "亏本清仓", "跳楼价", "史上最低"],
    "引导搜索": ["搜索", "找到我们", "认准", "旗舰店"],
    "违规营销": ["拼单", "刷单", "好评返现", "加微信"],
}

# 平台规则
PDD_RULES = {
    "max_length": 60,  # 更新：拼多多实际允许更长标题
    "best_min": 20,
    "best_max": 35,
    "core_word_zone": 15,  # 前15字是核心区
}

def match_keywords_from_db(product_info: str, top_n: int = 8) -> list:
    """根据商品描述从关键词库中智能匹配相关关键词"""
    if not KEYWORD_DB:
        return []

    scored = []
    product_lower = product_info.lower()

    for kw_text, kw_data in KEYWORD_DB.items():
        if len(kw_text) < 2:
            continue
        score = 0
        # 直接出现在商品描述中
        if kw_text in product_lower:
            score += 10
        # 关键词库中的高频词加分
        score += min(kw_data.get("total_count", 0), 5)
        # TF-IDF高的词加分
        score += kw_data.get("avg_tfidf_score", 0) * 2
        # 词性加分（品类词和属性词优先）
        word_type = kw_data.get("word_type", "")
        if word_type == "品类词":
            score += 3
        elif word_type == "属性词":
            score += 2
        elif word_type == "修饰词":
            score += 1

        if score > 0:
            scored.append((kw_text, score))

    scored.sort(key=lambda x: -x[1])
    return [w[0] for w in scored[:top_n]]

class TitleScorer:
    """标题5维度评分引擎"""

    def score(self, title: str, category: str = "", 
              top_keywords: list = None, product_info: str = "") -> dict:
        """
        对标题进行5维度评分
        """
        if top_keywords is None:
            if product_info:
                top_keywords = match_keywords_from_db(product_info)
            if not top_keywords:
                top_keywords = self._get_category_keywords(category)

        # 5个维度评分
        keyword_score, keyword_detail = self._score_keyword_coverage(title, top_keywords)
        compliance_score, compliance_detail = self._score_compliance(title)
        readability_score, readability_detail = self._score_readability(title)
        competition_score, competition_detail = self._score_competition(title)
        length_score, length_detail = self._score_length(title)

        # 加权总分
        weights = {
            "keyword_coverage": 0.35,
            "compliance": 0.25,
            "readability": 0.20,
            "competition": 0.10,
            "length": 0.10,
        }

        total = (
            keyword_score * weights["keyword_coverage"]
            + compliance_score * weights["compliance"]
            + readability_score * weights["readability"]
            + competition_score * weights["competition"]
            + length_score * weights["length"]
        )

        # 生成优化建议
        suggestions = self._generate_suggestions(
            title, keyword_score, compliance_score,
            readability_score, length_score,
            keyword_detail, compliance_detail, readability_detail, length_detail
        )

        return {
            "total_score": round(total, 1),
            "grade": self._get_grade(total),
            "dimensions": {
                "keyword_coverage": {"score": keyword_score, "weight": "35%", "detail": keyword_detail},
                "compliance": {"score": compliance_score, "weight": "25%", "detail": compliance_detail},
                "readability": {"score": readability_score, "weight": "20%", "detail": readability_detail},
                "competition_diff": {"score": competition_score, "weight": "10%", "detail": competition_detail},
                "length": {"score": length_score, "weight": "10%", "detail": length_detail},
            },
            "suggestions": suggestions,
            "char_count": len(title),
        }

    def _score_keyword_coverage(self, title: str, top_keywords: list) -> tuple:
        """维度1: 关键词覆盖率 (35%)"""
        if not top_keywords:
            return 60, {"matched": [], "missed": [], "msg": "未提供目标关键词，使用默认分数"}

        matched = [kw for kw in top_keywords if kw in title]
        missed = [kw for kw in top_keywords if kw not in title]

        coverage = len(matched) / len(top_keywords) * 100 if top_keywords else 0

        # 核心词在前15字加分
        core_zone = title[:PDD_RULES["core_word_zone"]]
        core_bonus = sum(5 for kw in matched if kw in core_zone)
        score = min(100, coverage + core_bonus)

        detail = {
            "matched": matched,
            "missed": missed,
            "coverage_pct": f"{coverage:.0f}%",
            "core_zone_bonus": core_bonus,
        }
        return round(score), detail

    def _score_compliance(self, title: str) -> tuple:
        """维度2: 平台合规性 (25%)"""
        score = 100
        issues = []

        # 检查禁用词
        for category, words in FORBIDDEN_WORDS.items():
            for word in words:
                if word in title:
                    if category == "极限词":
                        score -= 50
                    elif category == "引导搜索":
                        score -= 40
                    else:
                        score -= 30
                    issues.append(f"含{category}「{word}」")

        # 检查特殊符号（拼多多允许【】但不建议过多）
        special_count = len(re.findall(r'[★☆●○♥♡▲△■□◆◇]', title))
        if special_count > 0:
            score -= special_count * 10
            issues.append(f"含{special_count}个特殊符号")

        # emoji检查
        emoji_count = len(re.findall(r'[\U0001F000-\U0001F9FF]', title))
        if emoji_count > 0:
            score -= 20
            issues.append(f"含emoji符号")

        score = max(0, score)
        detail = {"issues": issues, "msg": "合规" if not issues else f"发现{len(issues)}个问题"}
        return score, detail

    def _score_readability(self, title: str) -> tuple:
        """维度3: 可读性 (20%)"""
        score = 80  # 基础分
        issues = []

        # 检查关键词堆砌（连续多个2字词没有连接）
        import jieba
        words = list(jieba.cut(title))
        short_word_streak = 0
        max_streak = 0
        for w in words:
            if len(w) <= 2 and w.strip():
                short_word_streak += 1
                max_streak = max(max_streak, short_word_streak)
            else:
                short_word_streak = 0

        if max_streak >= 6:
            score -= 20
            issues.append("关键词堆砌严重（连续6+个短词）")
        elif max_streak >= 4:
            score -= 10
            issues.append("轻度关键词堆砌")

        # 检查重复词
        word_counts = {}
        for w in words:
            if len(w) >= 2:
                word_counts[w] = word_counts.get(w, 0) + 1
        repeated = {w: c for w, c in word_counts.items() if c >= 2}
        if repeated:
            score -= len(repeated) * 5
            issues.append(f"重复词：{'、'.join(repeated.keys())}")

        # 标题是否有结构感（包含不同类型的词）
        has_category_word = any(kw in title for kw in ["裙", "衣", "裤", "壳", "膜", "霜", "刀", "笔", "杯", "袋"])
        has_modifier = any(kw in title for kw in ["显瘦", "百搭", "气质", "可爱", "便携", "耐用"])
        has_attribute = any(kw in title for kw in ["纯棉", "雪纺", "碎花", "加厚", "薄款", "防水", "软毛"])

        structure_score = sum([has_category_word, has_modifier, has_attribute])
        if structure_score >= 3:
            score += 10
        elif structure_score == 0:
            score -= 10
            issues.append("缺少结构感（建议包含品类词+属性词+修饰词）")

        score = max(0, min(100, score))
        detail = {"issues": issues, "word_count": len(words), "max_short_streak": max_streak}
        return score, detail

    def _score_competition(self, title: str) -> tuple:
        """维度4: 竞争差异度 (10%)"""
        # 简化版：检查标题是否使用了过于通用的表达
        generic_patterns = [
            "新款.*连衣裙.*显瘦",
            "夏季.*短袖.*女",
            "纯棉.*T恤.*宽松",
        ]
        is_generic = any(re.search(p, title) for p in generic_patterns)

        # 检查是否有独特元素
        unique_elements = []
        if re.search(r'[「」]', title):
            unique_elements.append("文艺标题符号")
        if re.search(r'【.*?】', title):
            unique_elements.append("标签式开头")
        if any(w in title for w in ["新中式", "赫本", "多巴胺", "森系", "桔梗"]):
            unique_elements.append("差异化风格词")

        score = 70 if is_generic else 85
        score += len(unique_elements) * 5
        score = min(100, score)

        detail = {
            "is_generic": is_generic,
            "unique_elements": unique_elements,
            "msg": "标题较为通用" if is_generic else "有一定差异化",
        }
        return score, detail

    def _score_length(self, title: str) -> tuple:
        """维度5: 字数合规性 (10%)"""
        length = len(title)

        if PDD_RULES["best_min"] <= length <= PDD_RULES["best_max"]:
            score = 100
            msg = f"字数{length}，处于最佳区间"
        elif length < 10:
            score = 20
            msg = f"字数{length}，过短，无法覆盖足够关键词"
        elif length < PDD_RULES["best_min"]:
            score = 60
            msg = f"字数{length}，偏短，建议增加属性词或修饰词"
        elif length <= PDD_RULES["max_length"]:
            score = 80
            msg = f"字数{length}，略长但可接受"
        else:
            score = 30
            msg = f"字数{length}，超出平台上限"

        detail = {"char_count": length, "msg": msg}
        return score, detail

    def _get_category_keywords(self, category: str) -> list:
        """根据品类返回推荐关键词 - 从关键词库动态获取"""
        # 先从关键词库中获取该品类高频词
        if KEYWORD_DB:
            cat_words = []
            for kw_text, kw_data in KEYWORD_DB.items():
                if kw_data.get("primary_category", "") == category:
                    cat_words.append((kw_text, kw_data.get("total_count", 0)))
                elif category and category in str(kw_data.get("categories", {})):
                    cat_words.append((kw_text, kw_data.get("total_count", 0)))

            if cat_words:
                # 按频次排序取Top 8
                cat_words.sort(key=lambda x: -x[1])
                return [w[0] for w in cat_words[:8]]

        # 兜底：固定关键词
        defaults = {
            "女装": ["连衣裙", "显瘦", "新款", "夏季", "气质", "收腰", "法式", "短袖"],
            "母婴": ["婴儿", "宝宝", "玩具", "新生儿", "早教", "纯棉", "薄款"],
            "家居日用": ["家用", "加厚", "耐用", "便携", "收纳", "食品级"],
            "零食": ["零食", "休闲", "整箱", "独立包装", "香辣", "坚果"],
            "美妆配饰": ["保湿", "补水", "持久", "显白", "新款", "学生"],
        }
        return defaults.get(category, ["新款", "品质", "热卖"])

    def _get_grade(self, score: float) -> str:
        if score >= 90: return "S 优秀"
        if score >= 80: return "A 良好"
        if score >= 70: return "B 中等"
        if score >= 60: return "C 及格"
        return "D 需优化"

    def _generate_suggestions(self, title, kw_score, comp_score, read_score, len_score,
                               kw_detail, comp_detail, read_detail, len_detail) -> list:
        suggestions = []

        if kw_score < 70 and kw_detail.get("missed"):
            missed = kw_detail["missed"][:3]
            suggestions.append(f"建议加入关键词：{'、'.join(missed)}")

        if comp_score < 100 and comp_detail.get("issues"):
            suggestions.append(f"合规问题：{comp_detail['issues'][0]}")

        if read_score < 70:
            if read_detail.get("issues"):
                suggestions.append(read_detail["issues"][0])

        if len_score < 80:
            suggestions.append(len_detail["msg"])

        if kw_score >= 80 and comp_score >= 90 and read_score >= 80:
            suggestions.append("标题质量不错！可以考虑A/B测试不同版本")

        return suggestions


# 全局单例
title_scorer = TitleScorer()