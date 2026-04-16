"""拼多多搜索下拉词采集"""

from datetime import datetime
from crawler.base import BaseCrawler


class PddSuggestCrawler(BaseCrawler):
    async def get_suggestions(self, keyword):
        page = await self.new_page()
        suggestions = []

        try:
            api_responses = []

            async def handle_response(response):
                if "suggest" in response.url or "search_suggest" in response.url:
                    try:
                        data = await response.json()
                        api_responses.append(data)
                    except Exception:
                        pass

            page.on("response", handle_response)

            await page.goto(
                f"https://mobile.yangkeduo.com/search_result.html?search_key={keyword}",
                wait_until="networkidle",
                timeout=30000,
            )
            await page.wait_for_timeout(3000)

            if not api_responses:
                search_input = page.locator('input[type="search"], input[placeholder*="搜索"]')
                if await search_input.count() > 0:
                    await search_input.first.click()
                    await page.wait_for_timeout(2000)

                    suggest_items = page.locator('.search-suggest-item, [class*="suggest"]')
                    count = await suggest_items.count()
                    for i in range(min(count, 20)):
                        text = await suggest_items.nth(i).text_content()
                        if text and text.strip():
                            suggestions.append({
                                "keyword": text.strip(),
                                "source": "dom",
                                "parent_keyword": keyword,
                                "crawled_at": datetime.now().isoformat(),
                            })

            for resp_data in api_responses:
                if isinstance(resp_data, dict):
                    items = resp_data.get("result", resp_data.get("data", []))
                    if isinstance(items, list):
                        for item in items:
                            word = item if isinstance(item, str) else item.get("word", item.get("keyword", ""))
                            if word:
                                suggestions.append({
                                    "keyword": word,
                                    "source": "api",
                                    "parent_keyword": keyword,
                                    "crawled_at": datetime.now().isoformat(),
                                })

        except Exception as e:
            print(f"采集 '{keyword}' 联想词出错：{e}")
        finally:
            await page.close()

        return suggestions

    async def batch_crawl(self, keywords):
        all_suggestions = []
        for i, kw in enumerate(keywords):
            print(f"  [{i+1}/{len(keywords)}] 采集：{kw}")
            results = await self.get_suggestions(kw)
            all_suggestions.extend(results)
            print(f"    获得 {len(results)} 个联想词")
            await self.random_delay()
        return all_suggestions