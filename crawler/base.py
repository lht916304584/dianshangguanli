"""爬虫基类 - 支持Cookie加载"""

import asyncio
import json
import os
import random
from playwright.async_api import async_playwright
from crawler.config import USER_AGENTS, MIN_DELAY, MAX_DELAY

COOKIE_PATH = "data/pdd_cookies.json"


class BaseCrawler:
    def __init__(self, headless=True):
        self.headless = headless
        self.browser = None
        self.playwright = None

    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )

    async def stop(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def new_page(self):
        context = await self.browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 375, "height": 812},
            is_mobile=True,
            locale="zh-CN",
        )

        # 加载Cookie
        if os.path.exists(COOKIE_PATH):
            with open(COOKIE_PATH, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)
            print("    ✅ 已加载Cookie")

        page = await context.new_page()
        await page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => false });"
        )
        return page

    async def random_delay(self):
        await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.stop()