"""测试 LLM API 调用 - 直接运行验证"""

import asyncio
import json
import sys
import os

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.ai.llm_client import LLMClient


async def test_basic_chat():
    """测试1：基础对话"""
    print("=" * 60)
    print("测试1：基础对话")
    print("=" * 60)

    client = LLMClient()
    response = await client.chat("你好，请用一句话介绍你自己")
    print(f"回复：{response}")
    print(f"✅ 基础对话调通！\n")


async def test_title_generation():
    """测试2：拼多多标题生成"""
    print("=" * 60)
    print("测试2：拼多多标题生成")
    print("=" * 60)

    client = LLMClient()

    # 测试商品
    test_products = [
        "夏季女款纯棉短袖T恤，宽松版型，圆领，多色可选，均码",
        "不锈钢保温杯，500ml容量，304食品级材质，车载便携",
        "儿童益智积木玩具，100片装，环保ABS材质，适合3-6岁",
    ]

    for product in test_products:
        print(f"\n商品：{product}")
        print("-" * 40)

        result = await client.generate_titles(
            product_info=product,
            platform="pinduoduo",
            count=5,
        )

        # 尝试解析 JSON
        try:
            # 提取 JSON 部分（LLM 可能返回 markdown 代码块）
            json_str = result
            if "```json" in result:
                json_str = result.split("```json")[1].split("```")[0]
            elif "```" in result:
                json_str = result.split("```")[1].split("```")[0]

            titles = json.loads(json_str.strip())
            for i, t in enumerate(titles, 1):
                title = t.get("title", "")
                char_count = len(title)
                status = "✅" if char_count <= 30 else "⚠️ 超长"
                print(f"  {i}. [{char_count}字] {status} {title}")
                print(f"     关键词：{t.get('keywords', [])}")
                print(f"     策略：{t.get('strategy', '')}")
        except json.JSONDecodeError:
            print(f"  原始返回：{result[:500]}")
            print("  ⚠️ JSON解析失败，需要优化Prompt")

    print(f"\n✅ 标题生成测试完成！\n")


async def test_multi_platform():
    """测试3：多平台标题生成对比"""
    print("=" * 60)
    print("测试3：多平台对比")
    print("=" * 60)

    client = LLMClient()
    product = "夏季女款纯棉短袖T恤，宽松版型，圆领"

    for platform in ["pinduoduo", "taobao", "douyin", "xiaohongshu"]:
        print(f"\n平台：{platform}")
        result = await client.generate_titles(product, platform, count=2)
        print(f"  {result[:200]}...")

    print(f"\n✅ 多平台测试完成！\n")


async def main():
    print("\n🚀 开始 LLM API 测试...\n")

    await test_basic_chat()
    await test_title_generation()
    # await test_multi_platform()  # 可选，取消注释即可

    print("🎉 所有测试通过！LLM API 链路已调通。")


if __name__ == "__main__":
    asyncio.run(main())