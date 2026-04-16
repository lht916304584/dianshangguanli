"""用AI生成拼多多风格的标题训练数据"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ai.llm_client import LLMClient


async def main():
    print("\n🤖 AI生成拼多多标题训练数据\n")
    os.makedirs("data", exist_ok=True)

    client = LLMClient()
    all_titles = []

    categories = [
        "女装（连衣裙、T恤、半身裙、外套）",
        "男装（T恤、短裤、衬衫、夹克）",
        "家居日用（保温杯、收纳盒、垃圾袋、拖鞋）",
        "手机配件（手机壳、数据线、充电宝、耳机）",
        "美妆护肤（面膜、洗面奶、防晒霜、口红）",
        "零食特产（坚果、饼干、辣条、水果干）",
        "母婴用品（纸尿裤、奶瓶、玩具、童装）",
        "运动户外（运动鞋、瑜伽垫、跳绳、背包）",
    ]

    for cat in categories:
        print(f"  生成品类：{cat}")
        prompt = f"""请生成15个真实的拼多多商品标题，品类是：{cat}

要求：
1. 每个标题严格控制在30字符以内
2. 模拟真实拼多多卖家的标题写法风格
3. 包含常见的属性词、修饰词、营销词
4. 有些标题质量好（关键词布局合理），有些质量一般（关键词堆砌或太短）
5. 不要用品牌名

请直接输出JSON数组格式，每个元素包含：
- title: 标题文本
- category: 品类名
- quality: "good" 或 "average" 或 "poor"（你对这个标题的质量判断）

只输出JSON，不要其他文字。"""

        try:
            result = await client.chat(prompt, temperature=0.9)
            # 提取JSON
            json_str = result
            if "```json" in result:
                json_str = result.split("```json")[1].split("```")[0]
            elif "```" in result:
                json_str = result.split("```")[1].split("```")[0]

            titles = json.loads(json_str.strip())
            all_titles.extend(titles)
            print(f"    ✅ 生成 {len(titles)} 条")
        except Exception as e:
            print(f"    ❌ 出错：{e}")

        await asyncio.sleep(1)

    # 保存
    with open("data/pdd_training_titles.json", "w", encoding="utf-8") as f:
        json.dump(all_titles, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"✅ 共生成 {len(all_titles)} 条标题训练数据")
    print(f"已保存到 data/pdd_training_titles.json")

    # 展示部分
    print(f"\n示例标题：")
    for t in all_titles[:10]:
        q = {"good": "✅好", "average": "⚠️中", "poor": "❌差"}.get(t.get("quality", ""), "")
        print(f"  {q} [{len(t['title'])}字] {t['title']}")

    print(f"\n💡 后续步骤：")
    print(f"  1. 从手机拼多多APP手动采集20-30条真实标题补充到数据中")
    print(f"  2. 用这些数据训练标题评分模型和Prompt优化")


if __name__ == "__main__":
    asyncio.run(main())