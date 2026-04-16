"""关键词库V2扩充 - 更细分、更真实"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ai.llm_client import LLMClient

async def generate_keywords(client, platform_name, category, sub_categories):
    """为某个品类的细分子类生成关键词"""
    all_kw = []
    
    prompt = f"""你是{platform_name}平台的资深电商运营专家，请为以下品类生成真实常用的商品标题关键词。

品类：{category}
细分子类：{sub_categories}

请生成80个关键词，严格分为以下4类：
1. 品类词（20个）：具体的商品名称和子品类名称，例如"连衣裙""碎花裙""A字裙"
2. 属性词（25个）：材质、规格、款式、版型、工艺等，例如"纯棉""加厚""高腰""收腰"
3. 修饰词（20个）：卖点、风格、感觉等，例如"显瘦""百搭""气质""ins风"
4. 营销词（15个）：场景、人群、促销等，例如"通勤""约会""学生""包邮""爆款"

要求：
- 必须是{platform_name}平台上卖家真实在用的词
- 每个词2-4个字
- 不要重复
- 不要包含品牌名

请严格按JSON格式输出：
[{{"word": "关键词", "type": "品类词/属性词/修饰词/营销词"}}]
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
            kw["category"] = category
        return keywords
    except Exception as e:
        print(f"    出错：{e}")
        return []


async def main():
    print("\n🔧 关键词库V2大规模扩充\n")
    os.makedirs("data", exist_ok=True)
    client = LLMClient()

    # 更细分的品类定义
    categories = {
        "女装": "连衣裙、半身裙、T恤、衬衫、卫衣、外套、裤子、短裤、牛仔裤、打底衫、吊带、西装、风衣、针织衫",
        "母婴": "纸尿裤、奶瓶、婴儿服装、玩具、推车、安全座椅、辅食、洗护、浴巾、睡袋、床品、早教、绘本、童鞋",
        "家居日用": "收纳、清洁工具、厨房用品、卫浴、毛巾、拖鞋、垃圾袋、保鲜膜、刀具、水杯、保温杯、文具、灯具、装饰",
        "零食": "坚果、饼干、肉干、糖果、果干、薯片、辣条、巧克力、蜜饯、膨化食品、方便面、特产、糕点、海味零食",
        "美妆配饰": "面膜、口红、防晒、洁面、精华、眼霜、粉底、腮红、眼影、卸妆、美甲、假睫毛、发饰、饰品",
    }

    platforms = [
        ("pinduoduo", "拼多多"),
        ("taobao", "淘宝/天猫"),
        ("douyin", "抖音"),
        ("xiaohongshu", "小红书"),
    ]

    for platform_id, platform_name in platforms:
        print(f"\n{'='*50}")
        print(f"平台：{platform_name}")
        print(f"{'='*50}")
        
        platform_keywords = []
        
        for cat, sub_cats in categories.items():
            print(f"  品类：{cat}...")
            keywords = await generate_keywords(client, platform_name, cat, sub_cats)
            platform_keywords.extend(keywords)
            print(f"    生成 {len(keywords)} 个关键词")
            await asyncio.sleep(1)

        # 去重
        seen = set()
        unique = []
        for kw in platform_keywords:
            word = kw.get("word", "")
            if word and word not in seen:
                seen.add(word)
                unique.append(kw)
        
        # 加载现有关键词
        existing_path = f"data/keywords_{platform_id}.json"
        if os.path.exists(existing_path):
            with open(existing_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            existing_words = set()
            for kw in existing:
                w = kw.get("word", kw.get("keyword", ""))
                existing_words.add(w)
            # 只添加新词
            new_count = 0
            for kw in unique:
                if kw["word"] not in existing_words:
                    existing.append(kw)
                    new_count += 1
            print(f"\n  {platform_name} 新增 {new_count} 个词，总计 {len(existing)} 个")
            with open(existing_path, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
        else:
            print(f"\n  {platform_name} 新建 {len(unique)} 个词")
            with open(existing_path, "w", encoding="utf-8") as f:
                json.dump(unique, f, ensure_ascii=False, indent=2)

    # 统计总数
    print(f"\n{'='*50}")
    print("📊 扩充后关键词库统计")
    print(f"{'='*50}")
    total = 0
    for pid, pname in platforms:
        p_path = f"data/keywords_{pid}.json"
        if os.path.exists(p_path):
            with open(p_path, "r", encoding="utf-8") as f:
                kws = json.load(f)
            print(f"  {pname}: {len(kws)} 个")
            total += len(kws)
    print(f"  总计: {total} 个关键词")

if __name__ == "__main__":
    asyncio.run(main())
