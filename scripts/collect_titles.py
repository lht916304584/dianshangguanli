"""拼多多标题数据采集 - 多种方式汇总"""

import asyncio
import json
import csv
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright


async def method1_manual_collect():
    """方式1：打开拼多多APP网页版，手动搜索后自动提取"""
    print("\n" + "=" * 50)
    print("方式1：半自动采集（你搜索，程序自动提取标题）")
    print("=" * 50)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 375, "height": 812},
            is_mobile=True,
            locale="zh-CN",
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
        )

        # 加载Cookie
        if os.path.exists("data/pdd_cookies.json"):
            with open("data/pdd_cookies.json", "r", encoding="utf-8") as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)

        page = await context.new_page()

        # 收集所有API响应中的商品数据
        all_goods = []

        async def capture_response(response):
            try:
                url = response.url
                if any(kw in url for kw in ["search", "goods", "product", "list"]):
                    if response.status == 200:
                        content_type = response.headers.get("content-type", "")
                        if "json" in content_type or "javascript" in content_type:
                            text = await response.text()
                            # 尝试提取商品标题
                            if "goods_name" in text or "title" in text:
                                try:
                                    data = json.loads(text)
                                    extract_goods(data, all_goods)
                                except Exception:
                                    pass
            except Exception:
                pass

        def extract_goods(data, results):
            """递归提取JSON中的商品数据"""
            if isinstance(data, dict):
                # 检查是否是商品对象
                name = data.get("goods_name") or data.get("title") or data.get("name", "")
                if name and len(name) > 5 and len(name) < 80:
                    item = {
                        "title": name,
                        "price": str(data.get("price", data.get("min_group_price", ""))),
                        "sales": str(data.get("sales_tip", data.get("cnt", ""))),
                    }
                    if item["title"] not in [r["title"] for r in results]:
                        results.append(item)
                # 递归搜索
                for v in data.values():
                    extract_goods(v, results)
            elif isinstance(data, list):
                for item in data:
                    extract_goods(item, results)

        page.on("response", capture_response)

        await page.goto("https://mobile.yangkeduo.com/", timeout=30000)
        await page.wait_for_timeout(3000)

        print("\n📱 浏览器已打开拼多多移动版！")
        print("\n请在浏览器中操作：")
        print("  1. 点击顶部搜索框")
        print("  2. 输入关键词（如：连衣裙）搜索")
        print("  3. 上下滚动浏览搜索结果")
        print("  4. 可以搜索多个关键词")
        print("\n程序会自动在后台捕获商品数据。")
        print("采集够了之后，回到终端按回车保存数据...\n")

        input("按回车保存采集结果...")

        # 额外等待一下确保数据都捕获到
        await page.wait_for_timeout(2000)

        print(f"\n📦 共捕获到 {len(all_goods)} 个商品标题")
        for i, g in enumerate(all_goods[:20], 1):
            print(f"  {i}. [{len(g['title'])}字] {g['title']}")
            if g.get("price"):
                print(f"     价格：{g['price']}")

        await browser.close()
        return all_goods


def method2_csv_import():
    """方式2：从CSV文件导入（手动整理的数据）"""
    print("\n" + "=" * 50)
    print("方式2：从CSV导入标题数据")
    print("=" * 50)

    csv_path = "data/pdd_titles_manual.csv"
    if not os.path.exists(csv_path):
        # 创建模板CSV
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["title", "category", "price", "sales"])
            writer.writerow(["示例：夏季纯棉短袖t恤女宽松圆领百搭上衣", "女装", "29.9", "10万+"])
            writer.writerow(["示例：304不锈钢保温杯大容量便携水杯", "日用品", "39.9", "5万+"])

        print(f"\n已创建模板文件：{csv_path}")
        print("请打开此CSV文件，填入你手动收集的拼多多商品标题数据")
        print("填好后重新运行此脚本\n")
        return []

    products = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row_data in reader:
            if row_data["title"] and not row_data["title"].startswith("示例"):
                products.append(dict(row_data))

    print(f"从CSV导入 {len(products)} 条数据")
    return products


def method3_generate_training_data():
    """方式3：用AI生成模拟训练数据（快速启动）"""
    print("\n" + "=" * 50)
    print("方式3：AI生成模拟标题数据（用于快速验证）")
    print("=" * 50)
    print("提示：可以让AI生成各品类的拼多多风格标题作为初始训练数据")
    print("后续再用真实数据替换\n")
    return []


async def main():
    print("\n🕷️ 拼多多标题数据采集工具\n")
    print("选择采集方式：")
    print("  1. 半自动采集（推荐！打开浏览器你搜索，程序后台抓数据）")
    print("  2. 从CSV文件导入（手动整理好的数据）")
    print("  3. 退出")

    choice = input("\n请选择 (1/2/3): ").strip()

    os.makedirs("data", exist_ok=True)
    products = []

    if choice == "1":
        products = await method1_manual_collect()
    elif choice == "2":
        products = method2_csv_import()
    else:
        print("退出")
        return

    if products:
        # 保存JSON
        with open("data/pdd_titles.json", "w", encoding="utf-8") as f:
            json.dump(products, f, ensure_ascii=False, indent=2)

        # 同时保存CSV方便查看
        with open("data/pdd_titles.csv", "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["title", "price", "sales"])
            writer.writeheader()
            for p in products:
                writer.writerow({
                    "title": p.get("title", ""),
                    "price": p.get("price", ""),
                    "sales": p.get("sales", ""),
                })

        print(f"\n✅ 数据已保存：")
        print(f"  JSON: data/pdd_titles.json ({len(products)} 条)")
        print(f"  CSV:  data/pdd_titles.csv")
    else:
        print("\n未采集到数据")


if __name__ == "__main__":
    asyncio.run(main())