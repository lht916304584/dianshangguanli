"""扩充多平台关键词库"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ai.llm_client import LLMClient

async def generate_platform_keywords(client, platform, platform_name):
    """为指定平台生成关键词"""
    categories = {
        "女装": "连衣裙、T恤、半身裙、裤子、外套",
        "母婴": "纸尿裤、奶瓶、玩具、童装、辅食",
        "家居日用": "收纳、清洁、厨房用品、卫浴、文具",
        "零食": "坚果、饼干、肉干、糖果、果干",
        "美妆配饰": "面膜、口红、防晒、护肤、美甲",
    }

    all_keywords = []
    for cat, examples in categories.items():
        print(f"  [{platform_name}] 生成品类：{cat}")
        prompt = f"""你是{platform_name}电商运营专家。请为以下品类生成{platform_name}平台最常用的标题关键词。

品类：{cat}（包括：{examples}）

请生成50个关键词，分为以下类型：
1. 品类词（10个）：商品品类名称
2. 属性词（15个）：材质、规格、款式、版型等
3. 修饰词（15个）：卖点、风格、感觉等
4. 营销词（10个）：促销、场景、人群等

要求：
- 必须是{platform_name}平台上真实常用的词
- 不同平台风格不同：拼多多偏实惠，淘宝偏品质，抖音偏潮流，小红书偏种草
- 每个词2-4个字

请严格按JSON格式输出：
```json
[
  {{"word": "关键词", "type": "品类词/属性词/修饰词/营销词", "category": "{cat}"}}
]
```
只输出JSON。"""

        try:
            result = await client.chat(prompt, temperature=0.8)
            json_str = result
            if "```json" in result:
                json_str = result.split("```json")[1].split("```")[0]
            elif "```" in result:
                json_str = result.split("```")[1].split("```")[0]
            keywords = json.loads(json_str.strip())
            for kw in keywords:
                kw["platform"] = platform
            all_keywords.extend(keywords)
            print(f"    生成 {len(keywords)} 个关键词")
        except Exception as e:
            print(f"    出错：{e}")
        await asyncio.sleep(1)

    return all_keywords


async def main():
    print("\n🔧 多平台关键词库扩充\n")
    os.makedirs("data", exist_ok=True)
    client = LLMClient()

    platforms = [
        ("taobao", "淘宝/天猫"),
        ("douyin", "抖音"),
        ("xiaohongshu", "小红书"),
    ]

    all_platform_keywords = {}

    for platform_id, platform_name in platforms:
        print(f"\n{'='*40}")
        print(f"生成 {platform_name} 关键词库")
        print(f"{'='*40}")
        keywords = await generate_platform_keywords(client, platform_id, platform_name)
        all_platform_keywords[platform_id] = keywords
        print(f"\n{platform_name} 共生成 {len(keywords)} 个关键词")

    # 加载现有拼多多关键词库
    pdd_path = "data/keyword_database.json"
    if os.path.exists(pdd_path):
        with open(pdd_path, "r", encoding="utf-8") as f:
            pdd_keywords = json.load(f)
        # 转换格式
        pdd_formatted = []
        for kw in pdd_keywords:
            pdd_formatted.append({
                "word": kw["keyword"],
                "type": kw.get("word_type", "其他"),
                "category": kw.get("primary_category", ""),
                "platform": "pinduoduo",
                "count": kw.get("total_count", 1),
            })
        all_platform_keywords["pinduoduo"] = pdd_formatted
        print(f"\n拼多多现有 {len(pdd_formatted)} 个关键词")

    # 合并保存
    combined = []
    for platform, keywords in all_platform_keywords.items():
        combined.extend(keywords)

    with open("data/keywords_all_platforms.json", "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)

    # 各平台单独保存
    for platform, keywords in all_platform_keywords.items():
        with open(f"data/keywords_{platform}.json", "w", encoding="utf-8") as f:
            json.dump(keywords, f, ensure_ascii=False, indent=2)

    # 统计
    print(f"\n{'='*40}")
    print(f"📊 关键词库统计")
    print(f"{'='*40}")
    total = 0
    for platform, keywords in all_platform_keywords.items():
        print(f"  {platform}: {len(keywords)} 个关键词")
        total += len(keywords)
    print(f"  总计: {total} 个关键词")
    print(f"\n💾 已保存到 data/ 目录")
    print(f"  keywords_all_platforms.json")
    for platform in all_platform_keywords:
        print(f"  keywords_{platform}.json")

if __name__ == "__main__":
    asyncio.run(main())
