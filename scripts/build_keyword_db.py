"""Day 3: 关键词分词入库Pipeline - 将标题数据分词后存入结构化数据库"""

import json
import re
import os
import sys
import csv
from collections import Counter
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import jieba
import jieba.analyse

# ===== 1. 加载电商专业词典 =====
def setup_jieba():
    """添加电商领域专业词汇到jieba词典"""
    ecom_words = [
        # 品类词
        "连衣裙","半身裙","包臀裙","百褶裙","鱼尾裙","碎花裙","吊带裙","公主裙","A字裙",
        "旗袍","卫衣","开衫","T恤","衬衫","哈衣","连体衣","包屁衣","阔腿裤","牛仔裤",
        "充电宝","移动电源","手机壳","数据线","蓝牙耳机","智能手表","智能手环",
        "面膜","口红","唇釉","唇膏","卸妆水","防晒霜","粉底液","BB霜","腮红","护手霜","眉刀",
        "纸尿裤","学步车","辅食机","隔尿垫",
        "垃圾袋","保鲜膜","沐浴球",
        "干脆面","鱿鱼仔","牛肉干",
        # 属性词
        "高腰","收腰","修身","中长款","方领","圆领","短袖","长袖",
        "加绒","加厚","薄款","超薄","大容量","食品级",
        "A字","盘扣","碎花","印花","波点","条纹","蕾丝","雪纺","纯棉",
        # 修饰词
        "显瘦","百搭","气质","设计感","高级感","小众","通勤","休闲",
        "法式","韩版","新中式","赫本","名媛","森系","ins风",
        "遮肚","遮肉","显白","小个子",
        # 功能词
        "保湿","补水","美白","提亮","遮瑕","控油","持久","哑光",
        "防水","防摔","防蚊","透气","防滑",
        "早教","益智","启蒙","安抚",
        "即食","解馋","开胃",
        # 人群词
        "婴幼儿","新生儿",
        # 品牌
        "三只松鼠","唐狮","婴蓓","科巢","帮宝适","好奇",
    ]
    for w in ecom_words:
        jieba.add_word(w, freq=10000)

    # 强制不拆分的词
    jieba.add_word("连衣裙", freq=50000)
    jieba.add_word("充电宝", freq=50000)
    jieba.add_word("蓝牙耳机", freq=50000)
    jieba.add_word("新中式", freq=50000)

setup_jieba()

# ===== 2. 加载标题数据 =====
def load_titles():
    """加载所有标题数据"""
    all_titles = []

    # 加载真实标题
    real_path = "data/pdd_real_titles_analyzed.json"
    if os.path.exists(real_path):
        with open(real_path, "r", encoding="utf-8") as f:
            real = json.load(f)
        for item in real:
            all_titles.append({
                "title": item["title"],
                "category": item.get("category", ""),
                "source": "real_pdd",
            })
        print(f"  加载真实标题：{len(real)} 条")

    # 加载AI生成标题
    ai_path = "data/pdd_training_titles.json"
    if os.path.exists(ai_path):
        with open(ai_path, "r", encoding="utf-8") as f:
            ai = json.load(f)
        for item in ai:
            all_titles.append({
                "title": item["title"],
                "category": item.get("category", ""),
                "source": "ai_generated",
            })
        print(f"  加载AI标题：{len(ai)} 条")

    return all_titles

# ===== 3. jieba分词 + 关键词提取 =====
def analyze_title(title):
    """对单条标题进行分词和关键词提取"""
    # 基础分词
    words = list(jieba.cut(title))
    # 过滤停用词和单字
    stopwords = {"的","了","和","与","或","在","是","有","个","件","款","装","新","女","男","夏","春","秋","冬"}
    meaningful_words = [w for w in words if len(w) >= 2 and w not in stopwords]

    # TF-IDF关键词提取
    keywords = jieba.analyse.extract_tags(title, topK=8, withWeight=True)

    # TextRank关键词提取
    textrank_kws = jieba.analyse.textrank(title, topK=5, withWeight=True)

    return {
        "all_words": words,
        "meaningful_words": meaningful_words,
        "tfidf_keywords": keywords,
        "textrank_keywords": textrank_kws,
    }

# ===== 4. 构建关键词数据库 =====
def build_keyword_database(titles_with_analysis):
    """构建关键词数据库"""
    keyword_db = {}

    for item in titles_with_analysis:
        title = item["title"]
        category = item.get("category", "未分类")
        analysis = item["analysis"]

        for word in analysis["meaningful_words"]:
            if word not in keyword_db:
                keyword_db[word] = {
                    "keyword": word,
                    "total_count": 0,
                    "categories": {},
                    "titles": [],
                    "tfidf_score_sum": 0,
                    "tfidf_count": 0,
                    "first_seen": datetime.now().isoformat(),
                    "word_length": len(word),
                }
            kw = keyword_db[word]
            kw["total_count"] += 1
            kw["categories"][category] = kw["categories"].get(category, 0) + 1
            if len(kw["titles"]) < 5:  # 最多存5条示例标题
                kw["titles"].append(title)

        # 记录TF-IDF分数
        for kw_text, score in analysis["tfidf_keywords"]:
            if kw_text in keyword_db:
                keyword_db[kw_text]["tfidf_score_sum"] += score
                keyword_db[kw_text]["tfidf_count"] += 1

    # 计算平均TF-IDF分数
    for kw in keyword_db.values():
        if kw["tfidf_count"] > 0:
            kw["avg_tfidf_score"] = round(kw["tfidf_score_sum"] / kw["tfidf_count"], 4)
        else:
            kw["avg_tfidf_score"] = 0
        # 计算主要品类
        if kw["categories"]:
            kw["primary_category"] = max(kw["categories"], key=kw["categories"].get)
        else:
            kw["primary_category"] = "未分类"
        # 清理临时字段
        del kw["tfidf_score_sum"]
        del kw["tfidf_count"]

    return keyword_db

# ===== 5. 词性标注 =====
def classify_word_type(word):
    """判断关键词的词性类型"""
    types = {
        "品类词": ["连衣裙","半身裙","包臀裙","百褶裙","鱼尾裙","碎花裙","吊带裙","公主裙","A字裙",
                  "旗袍","卫衣","开衫","T恤","短裙","长裙","裙子","中长裙",
                  "充电宝","手机壳","耳机","蓝牙耳机","数据线","智能手表","智能手环",
                  "面膜","口红","唇釉","唇膏","卸妆水","防晒霜","粉底液","腮红","护手霜","眉刀","美甲",
                  "纸尿裤","奶瓶","推车","学步车","玩具","摇铃","积木","辅食机","隔尿垫",
                  "垃圾袋","保鲜膜","沐浴球","牙刷","抹布","花盆","贴纸",
                  "零食","坚果","饼干","薯片","巧克力","糖果","牛肉干","鱿鱼仔","干脆面","虾条","果干"],
        "属性词": ["纯棉","雪纺","蕾丝","碎花","印花","条纹","波点",
                  "加厚","薄款","超薄","轻便","便携","折叠",
                  "收腰","修身","宽松","高腰","中长款","长款","短袖","方领","圆领","吊带",
                  "A字","盘扣","拼接","改良","两件套",
                  "大容量","食品级","防水","透气","独立包装","软毛"],
        "修饰词": ["显瘦","百搭","气质","设计感","高级感","复古","法式","新中式","韩版",
                  "新款","清新","甜美","温柔","可爱","赫本","名媛","森系","ins风",
                  "遮肚","遮肉","显白","小个子","小众","休闲","通勤","耐用","时尚"],
        "功能词": ["保湿","补水","美白","提亮","遮瑕","控油","持久","哑光",
                  "防蚊","防摔","防滑","降噪",
                  "早教","益智","启蒙","安抚",
                  "香辣","即食","解馋","开胃","酸甜"],
        "人群词": ["儿童","婴儿","婴幼儿","新生儿","宝宝","学生","孕妇","男女"],
        "季节词": ["夏季","春秋","秋冬","春夏","春季"],
    }
    for type_name, words in types.items():
        if word in words:
            return type_name
    return "其他"

# ===== 主程序 =====
def main():
    print("\n🔧 关键词入库Pipeline")
    print("=" * 60)

    os.makedirs("data", exist_ok=True)

    # Step 1: 加载数据
    print("\n📥 Step 1: 加载标题数据")
    titles = load_titles()
    print(f"  总计：{len(titles)} 条标题")

    # Step 2: jieba分词分析
    print(f"\n🔪 Step 2: jieba分词分析")
    for item in titles:
        item["analysis"] = analyze_title(item["title"])
    print(f"  分词完成！")

    # 展示几个分词示例
    print(f"\n  分词示例：")
    for item in titles[:5]:
        words = " | ".join(item["analysis"]["meaningful_words"])
        print(f"    {item['title'][:25]}...")
        print(f"    → {words}")

    # Step 3: 构建关键词数据库
    print(f"\n📦 Step 3: 构建关键词数据库")
    keyword_db = build_keyword_database(titles)

    # 添加词性标注
    for kw in keyword_db.values():
        kw["word_type"] = classify_word_type(kw["keyword"])

    print(f"  共提取 {len(keyword_db)} 个关键词")

    # Step 4: 统计展示
    print(f"\n📊 Step 4: 关键词统计")

    # 按频次排序Top 30
    sorted_kws = sorted(keyword_db.values(), key=lambda x: -x["total_count"])
    print(f"\n  频次 TOP 20：")
    for i, kw in enumerate(sorted_kws[:20], 1):
        bar = "█" * kw["total_count"]
        print(f"    {i:2d}. [{kw['word_type']:<4s}] {kw['keyword']:<8s} {kw['total_count']:3d}次 {bar}")

    # 按TF-IDF分数排序Top 20
    sorted_tfidf = sorted(keyword_db.values(), key=lambda x: -x["avg_tfidf_score"])
    print(f"\n  TF-IDF价值 TOP 20（独特性高的词）：")
    for i, kw in enumerate(sorted_tfidf[:20], 1):
        print(f"    {i:2d}. [{kw['word_type']:<4s}] {kw['keyword']:<8s} TF-IDF={kw['avg_tfidf_score']:.4f}  出现{kw['total_count']}次")

    # 按词性分组统计
    type_counts = {}
    for kw in keyword_db.values():
        t = kw["word_type"]
        type_counts[t] = type_counts.get(t, 0) + 1
    print(f"\n  词性分布：")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"    {t}：{c} 个词")

    # Step 5: 保存数据库
    print(f"\n💾 Step 5: 保存关键词数据库")

    # JSON格式（完整数据）
    db_list = sorted(keyword_db.values(), key=lambda x: -x["total_count"])
    with open("data/keyword_database.json", "w", encoding="utf-8") as f:
        json.dump(db_list, f, ensure_ascii=False, indent=2)

    # CSV格式（方便查看和导入数据库）
    with open("data/keyword_database.csv", "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["keyword","word_type","total_count","avg_tfidf","primary_category","word_length"])
        for kw in db_list:
            writer.writerow([
                kw["keyword"],
                kw["word_type"],
                kw["total_count"],
                kw["avg_tfidf_score"],
                kw["primary_category"],
                kw["word_length"],
            ])

    # 分词后的完整标题数据
    export_titles = []
    for item in titles:
        export_titles.append({
            "title": item["title"],
            "category": item.get("category", ""),
            "source": item.get("source", ""),
            "words": item["analysis"]["meaningful_words"],
            "tfidf_top5": [(w, round(s, 4)) for w, s in item["analysis"]["tfidf_keywords"][:5]],
        })
    with open("data/titles_tokenized.json", "w", encoding="utf-8") as f:
        json.dump(export_titles, f, ensure_ascii=False, indent=2)

    print(f"  keyword_database.json  （{len(db_list)} 个关键词完整数据）")
    print(f"  keyword_database.csv   （CSV格式，可导入Excel/数据库）")
    print(f"  titles_tokenized.json  （{len(export_titles)} 条标题分词结果）")

    print(f"\n✅ 关键词入库Pipeline完成！")
    print(f"\n💡 下一步：")
    print(f"  1. 将keyword_database.csv导入PostgreSQL数据库")
    print(f"  2. 搭建向量数据库，将关键词向量化存入Milvus")
    print(f"  3. 基于关键词库优化标题生成Prompt")

if __name__ == "__main__":
    main()