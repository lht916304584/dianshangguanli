"""拼多多搜索建议API采集 - 直接请求接口，更稳定"""

import asyncio
import random
import httpx
from datetime import datetime
from crawler.config import USER_AGENTS, MIN_DELAY, MAX_DELAY


class PddSuggestApiCrawler:
    def __init__(self):
        self.client = None

    async def start(self):
        self.client = httpx.AsyncClient(timeout=15, follow_redirects=True)

    async def stop(self):
        if self.client:
            await self.client.aclose()

    async def get_suggestions(self, keyword):
        """通过拼多多移动端搜索建议接口获取联想词"""
        suggestions = []
        
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Referer": "https://mobile.yangkeduo.com/",
            "Accept": "application/json",
        }

        # 拼多多搜索建议接口
        urls = [
            f"https://apiv2.yangkeduo.com/search/suggest?keyword={keyword}",
            f"https://mobile.yangkeduo.com/proxy/api/search/suggest?keyword={keyword}",
        ]

        for url in urls:
            try:
                resp = await self.client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    words = self._extract_words(data, keyword)
                    if words:
                        suggestions.extend(words)
                        break
            except Exception:
                continue

        # 如果API不通，用备选方案：搜索页面标题提取
        if not suggestions:
            suggestions = await self._fallback_search(keyword, headers)

        return suggestions

    def _extract_words(self, data, parent_keyword):
        """从API响应中提取联想词"""
        words = []
        
        # 尝试多种响应格式
        candidates = []
        if isinstance(data, list):
            candidates = data
        elif isinstance(data, dict):
            for key in ["result", "data", "suggest_list", "words", "list"]:
                if key in data:
                    candidates = data[key]
                    break

        for item in candidates:
            word = ""
            if isinstance(item, str):
                word = item
            elif isinstance(item, dict):
                for k in ["word", "keyword", "text", "sug_word", "name"]:
                    if k in item:
                        word = item[k]
                        break

            if word and word.strip():
                words.append({
                    "keyword": word.strip(),
                    "source": "api",
                    "parent_keyword": parent_keyword,
                    "crawled_at": datetime.now().isoformat(),
                })

        return words

    async def _fallback_search(self, keyword, headers):
        """备选方案：从搜索结果页提取商品标题中的关键词"""
        suggestions = []
        try:
            url = f"https://mobile.yangkeduo.com/proxy/api/search?keyword={keyword}&page=1&size=20"
            resp = await self.client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("result", data.get("data", data.get("goods_list", [])))
                if isinstance(items, list):
                    for item in items[:20]:
                        title = ""
                        if isinstance(item, dict):
                            title = item.get("goods_name", item.get("title", item.get("name", "")))
                        if title:
                            suggestions.append({
                                "keyword": title.strip(),
                                "source": "search_title",
                                "parent_keyword": keyword,
                                "crawled_at": datetime.now().isoformat(),
                            })
        except Exception as e:
            print(f"    备选方案也失败：{e}")

        return suggestions

    async def batch_crawl(self, keywords):
        """批量采集"""
        all_suggestions = []
        for i, kw in enumerate(keywords):
            print(f"  [{i+1}/{len(keywords)}] 采集：{kw}")
            results = await self.get_suggestions(kw)
            all_suggestions.extend(results)
            print(f"    获得 {len(results)} 个联想词")
            await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
        return all_suggestions

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.stop()