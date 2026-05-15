"""详情图AI策划引擎 — 卖点提炼 + 页面结构 + 图片提示词"""

import json

from app.ai.llm_client import llm_client
from app.ai.image_generator import image_generator

PLATFORM_CONTEXT = {
    "pinduoduo": "拼多多用户价格敏感，强调性价比和实惠，文案要接地气",
    "taobao": "淘宝用户注重品质和品牌感，文案要体现专业和信任",
    "douyin": "抖音用户追求新奇和视觉冲击，文案要短平快、有网感",
    "xiaohongshu": "小红书用户喜欢真实种草感，文案要自然、有活人感",
}


class DetailPlanner:

    async def run(self, product_info: str, platform: str, category: str, llm=None) -> dict:
        selling_points = await self._extract_selling_points(product_info, category, llm=llm)
        page_structure = await self._generate_page_structure(selling_points, platform, product_info, llm=llm)
        image_prompts = await self._generate_image_prompts(page_structure, product_info, llm=llm)

        # 预留图片生成（当前仅提示词）
        images = []
        for prompt in image_prompts:
            result = await image_generator.generate(prompt)
            images.append(result)

        return {
            "success": True,
            "selling_points": selling_points,
            "page_structure": page_structure,
            "image_prompts": image_prompts,
            "images": images,
            "product_info": product_info,
            "platform": platform,
        }

    async def _extract_selling_points(self, product_info: str, category: str, llm=None) -> dict:
        prompt = f"""你是一位资深电商运营专家，请根据以下商品信息提炼卖点。

商品信息：{product_info}
品类：{category or "通用"}

请按以下JSON格式输出（不要输出其他内容）：
{{
  "core_points": [
    {{"title": "核心卖点1（4-8字）", "detail": "具体说明（15-30字）"}},
    {{"title": "核心卖点2", "detail": "..."}},
    {{"title": "核心卖点3", "detail": "..."}}
  ],
  "support_points": [
    {{"title": "支撑卖点1", "detail": "..."}},
    {{"title": "支撑卖点2", "detail": "..."}},
    {{"title": "支撑卖点3", "detail": "..."}},
    {{"title": "支撑卖点4", "detail": "..."}},
    {{"title": "支撑卖点5", "detail": "..."}}
  ],
  "evidence": ["证据1（如：月销10000+）", "证据2（如：99%好评率）", "证据3（如：质检报告）"],
  "pain_points": ["用户痛点1", "用户痛点2", "用户痛点3"]
}}

要求：
- 核心卖点必须是最能打动买家的3个差异化优势
- 支撑点用来强化核心卖点，可以包含材质、工艺、设计、服务等
- 证据要具体可信，用数据或权威背书
- 痛点要切中目标用户的真实困扰"""

        system = "你是电商详情页策划专家，擅长提炼产品卖点和用户心理分析。只输出JSON。"
        client = llm or llm_client
        raw = await client.chat(prompt, system_prompt=system, temperature=0.7, max_tokens=2000)
        return self._parse_json(raw, {
            "core_points": [], "support_points": [], "evidence": [], "pain_points": []
        })

    async def _generate_page_structure(
        self, selling_points: dict, platform: str, product_info: str, llm=None
    ) -> list:
        platform_ctx = PLATFORM_CONTEXT.get(platform, "")
        points_desc = json.dumps(selling_points, ensure_ascii=False, indent=2)

        prompt = f"""你是一位资深电商详情页策划专家，请为以下商品生成详情页文案策划。

商品信息：{product_info}
平台特点：{platform_ctx}

已提炼的卖点信息：
{points_desc}

请生成6屏详情页结构，每屏包含标题、正文文案、设计建议。输出JSON数组格式（不要输出其他内容）：
[
  {{
    "screen": 1,
    "type": "主图+核心卖点",
    "title": "页面主标题（10-20字，有冲击力）",
    "subtitle": "副标题（补充说明，10-15字）",
    "body": "核心卖点描述文案（30-50字）",
    "design_tip": "设计风格建议（如：简洁白底、产品居中、卖点标注）"
  }},
  {{
    "screen": 2,
    "type": "痛点场景",
    "title": "痛点标题",
    "subtitle": "",
    "body": "描述用户痛点场景（40-60字，引发共鸣）",
    "design_tip": "设计建议"
  }},
  {{
    "screen": 3,
    "type": "卖点展示1",
    "title": "卖点标题",
    "subtitle": "卖点副标题",
    "body": "卖点详细描述（30-50字）",
    "design_tip": "设计建议"
  }},
  {{
    "screen": 4,
    "type": "卖点展示2",
    "title": "卖点标题",
    "subtitle": "",
    "body": "卖点描述",
    "design_tip": "设计建议"
  }},
  {{
    "screen": 5,
    "type": "卖点展示3+参数",
    "title": "卖点/参数标题",
    "subtitle": "",
    "body": "卖点描述 + 关键参数对比",
    "design_tip": "设计建议"
  }},
  {{
    "screen": 6,
    "type": "促销+行动号召",
    "title": "促销标题",
    "subtitle": "",
    "body": "促转文案（20-40字，包含限时优惠、已售数量等紧迫感元素）",
    "design_tip": "设计建议"
  }}
]

要求：
- 每屏标题要简洁有力，直接说清这一屏的核心信息
- 文案风格匹配{platform}平台用户偏好
- 避免极限词和违规内容
- 第1屏必须包含最强卖点
- 第6屏要制造紧迫感促成下单"""

        system = "你是电商详情页文案策划专家，擅长高转化率页面设计。只输出JSON数组。"
        client = llm or llm_client
        raw = await client.chat(prompt, system_prompt=system, temperature=0.7, max_tokens=3000)
        result = self._parse_json(raw, [])
        if isinstance(result, dict) and "screens" in result:
            result = result["screens"]
        return result if isinstance(result, list) else []

    async def _generate_image_prompts(self, page_structure: list, product_info: str, llm=None) -> list:
        if not page_structure:
            return []

        screens_desc = "\n".join(
            f"第{s.get('screen', i+1)}屏-{s.get('type', '')}: {s.get('title', '')} — {s.get('body', '')[:60]}"
            for i, s in enumerate(page_structure)
        )

        prompt = f"""请为以下电商详情页的每一屏生成图片描述提示词（英文），用于AI生图。

商品：{product_info}

页面结构：
{screens_desc}

输出JSON数组，每项包含screen和prompt字段：
[
  {{"screen": 1, "prompt": "English image generation prompt, detailed, e-commerce product photography style, ..."}},
  ...
]

提示词要求：
- 用英文描述，便于AI图片生成模型理解
- 包含构图、光线、色彩、风格等细节
- 电商产品摄影风格为主
- 每条提示词50-100个英文单词
- 不要包含任何品牌名称或logo描述"""

        system = "You are an expert in AI image prompt engineering for e-commerce product photography. Output JSON array only."
        client = llm or llm_client
        raw = await client.chat(prompt, system_prompt=system, temperature=0.7, max_tokens=2000)
        result = self._parse_json(raw, [])
        if isinstance(result, list):
            return [item.get("prompt", "") if isinstance(item, dict) else str(item) for item in result]
        return []

    def _parse_json(self, text: str, fallback):
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("[")
            end = text.rfind("]")
            if start != -1 and end != -1:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    pass
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    pass
            return fallback


detail_planner = DetailPlanner()
