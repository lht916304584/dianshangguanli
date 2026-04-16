"""拼多多商品标题采集 - 网页版"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright


async def crawl_pdd_titles(keyword, max_count=50):
    """用网页版拼多多采集商品标题"""
    print(f"\n🔍 搜索关键词：{keyword}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
        )

        # 加载Cookie
        cookie_path = "data/pdd_cookies.json"
        if os.path.exists(cookie_path):
            with open(cookie_path, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)
            print("  ✅ 已加载Cookie")

        page = await context.new_page()

        # 用拼多多网页搜索
        url = f"https://www.yangkeduo.com/search_result.html?search_key={keyword}"
        print(f"  访问：{url}")

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(5000)

            # 如果需要登录，等待手动操作
            page_url = page.url
            if "login" in page_url or "passport" in page_url:
                print("\n  ⚠️ 需要登录！请在浏览器中完成登录...")
                print("  登录完成后按回车继续...")
                input()
                # 重新保存Cookie
                new_cookies = await context.cookies()
                with open(cookie_path, "w", encoding="utf-8") as f:
                    json.dump(new_cookies, f, ensure_ascii=False, indent=2)
                print(f"  ✅ 已更新Cookie")
                # 重新访问搜索页
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(5000)

            # 滚动加载更多
            for i in range(3):
                await page.evaluate("window.scrollBy(0, 1000)")
                await page.wait_for_timeout(2000)

            # 获取页面所有文本内容，用多种选择器尝试
            products = []

            # 方法1：通过标题相关的选择器
            selectors = [
                'a[title]',
                '[class*="title"]',
                '[class*="name"]',
                '[class*="goods"]',
                '.search-item',
            ]

            for sel in selectors:
                items = page.locator(sel)
                count = await items.count()
                if count > 3:
                    print(f"  选择器 '{sel}' 找到 {count} 个元素")
                    for i in range(min(count, max_count)):
                        try:
                            el = items.nth(i)
                            # 优先取title属性
                            title = await el.get_attribute("title") or ""
                            if not title:
                                title = await el.text_content() or ""
                            title = title.strip()
                            if title and len(title) > 5 and len(title) < 60:
                                if title not in [p["title"] for p in products]:
                                    products.append({
                                        "title": title,
                                        "keyword": keyword,
                                        "selector": sel,
                                    })
                        except Exception:
                            continue
                    if len(products) >= 10:
                        break

            # 方法2：如果选择器都没用，截图看页面结构
            if len(products) < 5:
                print("  📸 选择器匹配较少，保存截图供分析...")
                await page.screenshot(path="data/pdd_search_page.png", full_page=True)
                print("  截图已保存到 data/pdd_search_page.png")

                # 尝试获取页面上所有链接的title
                all_links = page.locator("a")
                link_count = await all_links.count()
                print(f"  页面共有 {link_count} 个链接，扫描中...")
                for i in range(min(link_count, 200)):
                    try:
                        link = all_links.nth(i)
                        title = await link.get_attribute("title") or ""
                        href = await link.get_attribute("href") or ""
                        if title and len(title) > 8 and "goods" in href:
                            if title not in [p["title"] for p in products]:
                                products.append({
                                    "title": title,
                                    "keyword": keyword,
                                    "selector": "a[title]+goods_href",
                                })
                    except Exception:
                        continue

            print(f"\n  📦 共采集到 {len(products)} 个商品标题")
            for i, p_item in enumerate(products[:20], 1):
                print(f"    {i}. [{len(p_item['title'])}字] {p_item['title']}")

            return products

        except Exception as e:
            print(f"  ❌ 出错：{e}")
            await page.screenshot(path="data/pdd_error.png")
            print("  错误截图已保存到 data/pdd_error.png")
            return []

        finally:
            await browser.close()


async def main():
    print("\n🕷️ 拼多多商品标题采集工具\n")
    os.makedirs("data", exist_ok=True)

    all_products = []
    keywords = ["连衣裙", "保温杯"]

    for kw in keywords:
        products = await crawl_pdd_titles(kw, max_count=30)
        all_products.extend(products)

    # 保存结果
    with open("data/pdd_titles.json", "w", encoding="utf-8") as f:
        json.dump(all_products, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"✅ 总计采集 {len(all_products)} 个商品标题")
    print(f"已保存到 data/pdd_titles.json")

    if len(all_products) == 0:
        print("\n💡 如果采集不到数据，请查看 data/pdd_search_page.png 截图")
        print("   截图会展示页面实际结构，我可以帮你调整选择器")


if __name__ == "__main__":
    asyncio.run(main())