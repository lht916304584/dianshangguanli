"""测试标题评分引擎"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ai.title_scorer import title_scorer

# 测试标题
test_cases = [
    ("法式碎花方领短袖连衣裙女夏季新款收腰显瘦设计感中长裙", "女装"),
    ("裙子好看", "女装"),
    ("最好的连衣裙全网最低价独家限时抢购", "女装"),
    ("婴蓓婴儿纯棉小方巾新生儿a类口水巾宝宝纱布毛巾洗脸巾儿童用品", "母婴"),
    ("【爆款新品】自嗨炉炭烤棉花糖套装男女友礼物休闲儿童零食", "零食"),
    ("加厚抽绳垃圾袋塑料袋家用手提式自动收口大号", "家居日用"),
    ("「晚风清梦」复古法式杏色连衣裙女夏新款短袖度假长款裙子", "女装"),
    ("折叠眉刀修眉刀刮眉刀唇毛初学者懒人专用新款修眉神器", "美妆配饰"),
]

print("\n📊 标题评分引擎测试")
print("=" * 60)

for title, category in test_cases:
    result = title_scorer.score(title, category)

    print(f"\n{'─' * 50}")
    print(f"📝 标题：{title}")
    print(f"📂 品类：{category}  |  📏 字数：{result['char_count']}")
    print(f"\n   🏆 总分：{result['total_score']} / 100  ({result['grade']})")
    print(f"\n   各维度：")
    for dim_name, dim in result["dimensions"].items():
        names = {
            "keyword_coverage": "关键词覆盖",
            "compliance": "平台合规",
            "readability": "可读性",
            "competition_diff": "竞争差异",
            "length": "字数合规",
        }
        bar = "█" * (dim["score"] // 10) + "░" * (10 - dim["score"] // 10)
        print(f"     {names.get(dim_name, dim_name):<8s} {bar} {dim['score']:3d}分 ({dim['weight']})")

    if result["suggestions"]:
        print(f"\n   💡 优化建议：")
        for s in result["suggestions"]:
            print(f"     → {s}")

print(f"\n{'=' * 60}")
print("✅ 评分引擎测试完成！")