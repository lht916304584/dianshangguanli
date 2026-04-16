"""拼多多登录 - 手动登录后保存Cookie供爬虫使用"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright


async def main():
    print("\n🔐 拼多多登录工具")
    print("=" * 50)
    print("步骤：")
    print("1. 马上会弹出浏览器窗口")
    print("2. 请手动完成登录（扫码或手机号）")
    print("3. 登录成功后，在终端按回车键保存Cookie")
    print("=" * 50)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
        )
        page = await context.new_page()

        # 打开拼多多商家后台或移动端
        await page.goto("https://mobile.yangkeduo.com/")
        
        input("\n✅ 登录成功后，按回车键保存Cookie...")

        # 保存Cookie
        cookies = await context.cookies()
        os.makedirs("data", exist_ok=True)
        with open("data/pdd_cookies.json", "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)

        print(f"\n🎉 已保存 {len(cookies)} 个Cookie到 data/pdd_cookies.json")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())