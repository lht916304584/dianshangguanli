"""LLM 客户端封装 - 支持 DeepSeek / Qwen 多模型切换"""

from openai import AsyncOpenAI
from app.core.config import settings


class LLMClient:
    """统一的 LLM 调用客户端"""

    def __init__(self, api_key=None, base_url=None, model=None):
        self.client = AsyncOpenAI(
            api_key=api_key or settings.DEEPSEEK_API_KEY,
            base_url=base_url or settings.DEEPSEEK_BASE_URL,
        )
        self.model = model or settings.DEFAULT_LLM_MODEL

    async def chat(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """基础对话调用"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    async def generate_titles(
        self,
        product_info: str,
        platform: str = "pinduoduo",
        count: int = 5,
    ) -> str:
        """生成电商标题（基础版，后续会用 RAG 增强）"""
        system_prompt = self._get_platform_system_prompt(platform)
        user_prompt = self._build_title_prompt(product_info, platform, count)
        return await self.chat(user_prompt, system_prompt, temperature=0.8)

    def _get_platform_system_prompt(self, platform: str) -> str:
        """各平台的系统 Prompt"""
        prompts = {
            "pinduoduo": """你是一个资深的拼多多运营专家，精通拼多多搜索算法和标题优化。
你深知以下拼多多标题规则：
1. 标题总长度不超过30个字符
2. 禁止使用极限词（最、第一、顶级等）
3. 禁止未授权使用品牌词
4. 禁止引导搜索词（如"搜索XX找到我们"）
5. 核心关键词尽量放在标题前半部分
6. 拼多多算法偏好精确匹配，全标题匹配权重极高
7. 标题要兼顾搜索流量和点击率
8. 属性词+核心词+长尾词的组合结构效果最好""",

            "taobao": """你是一个资深的天猫/淘宝运营专家，精通淘系搜索算法。
标题规则：总长度不超过60个字符，品牌词前置，关键词相关性权重高，前半部分权重更高。""",

            "douyin": """你是一个资深的抖音电商运营专家。
标题规则：不超过30字符，需同时优化搜索标题和内容标签，"看后搜"场景重要。""",

            "xiaohongshu": """你是一个资深的小红书运营专家。
标题规则：不超过20字符，可用emoji，重可读性，语言风格自然，避免关键词堆砌。""",
        }
        return prompts.get(platform, prompts["pinduoduo"])

    def _build_title_prompt(
        self, product_info: str, platform: str, count: int
    ) -> str:
        """构建标题生成 Prompt V2 - 融入真实数据规律"""
        platform_names = {
            "pinduoduo": "拼多多",
            "taobao": "天猫/淘宝",
            "douyin": "抖音",
            "xiaohongshu": "小红书",
        }
        pname = platform_names.get(platform, "拼多多")

        if platform == "pinduoduo":
            return f"""请为以下商品生成{count}个高质量的{pname}商品标题。

商品信息：{product_info}

## 拼多多标题写作规则（必须严格遵守）

### 字数规则
- 标题长度控制在28-30个字，必须写满接近30个字
- 绝对不能低于25字，低于25字会严重影响搜索曝光

### 标题结构公式
使用以下结构：核心搜索词 + 属性词 + 修饰词 + 长尾词/营销词
- 核心搜索词放在前15个字以内（拼多多算法对前半部分权重更高）
- 属性词描述材质/规格/款式（如：纯棉、雪纺、碎花、高腰、A字）
- 修饰词增加点击欲望（如：显瘦、百搭、气质、收腰、设计感）
- 长尾词覆盖更多搜索场景（如：通勤、日常、休闲、送礼）

### 高分标题的6个特征
1. 包含至少2个属性词（材质/版型/款式）
2. 包含至少1个修饰词（显瘦/气质/百搭等）
3. 核心品类词在前10字出现
4. 季节词+年份增加时效感（如"2026夏季新款"）
5. 自然通顺不堆砌，读起来像完整的商品描述
6. 与竞品标题有差异化（避免千篇一律）

### 禁止使用（严格遵守）
- 极限词：最好、最低价、第一、顶级、极品
- 所有品牌名：禁止使用任何品牌名称（如良良、十月结晶、全棉时代、南极人等），即使是知名品牌也不能用
- 引导搜索词：搜索XX找到我们
- emoji和特殊符号：★☆●○等
- 注意：标题中只能使用通用品类词和属性词，绝对不能出现任何品牌名

### 真实拼多多TOP标题参考（学习这些标题的写法风格和长度）
- 凡兔法式方领黑色连衣裙女2026夏季新款复古气质收腰显瘦中长裙子（32字）
- 法式蕾丝拼接条纹短袖连衣裙女2026夏季新款收腰显瘦设计感中长裙（31字）
- 婴蓓婴儿纯棉小方巾新生儿a类口水巾宝宝纱布毛巾洗脸巾儿童用品（30字）
- 加贝鲜带籽鱿鱼仔香辣烧烤即食海鲜墨鱼类熟食休闲解馋小零食整箱（31字）
- 【养出漫画手】香氛护手霜滋润保湿补水干裂专用清爽持久学生四季（30字）

请按以下格式输出（严格JSON格式）：
```json
[
  {{
    "title": "生成的标题（25-35字）",
    "keywords": ["核心词1", "核心词2", "属性词1", "修饰词1"],
    "strategy": "一句话说明这个标题的关键词策略和卖点"
  }}
]
```

注意：
- 每个标题的关键词组合策略必须有差异
- 标题长度必须在28-30字之间，尽量写满30字
- 只输出JSON，不要其他解释文字"""

        return f"""请为以下商品生成{count}个优化的{pname}商品标题。
商品信息：{product_info}
请按JSON格式输出，每个标题包含 title, keywords, strategy 三个字段。
标题长度25-35字，核心搜索词放前半部分，包含属性词和修饰词。
只输出JSON。"""

# 全局单例
llm_client = LLMClient()