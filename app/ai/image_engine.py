"""AI 生图引擎 — 支持用户自管 API Key（OpenAI DALL-E 兼容格式）"""

import httpx

from app.ai.llm_client import llm_client


class ImageEngine:
    """通用生图引擎，调用用户配置的第三方 API。"""

    async def generate(
        self,
        prompt: str,
        config: dict,
        image_type: str = "main",
        count: int = 1,
    ) -> dict:
        """
        生成图片。

        Args:
            prompt: 用户输入的中文/英文提示词
            config: {api_key, base_url, model, size}
            image_type: "main" | "detail"
            count: 生成数量 1-4

        Returns:
            {"urls": [...], "prompt": enhanced_prompt, "status": "success"|"error", "error": str}
        """
        api_key = config.get("api_key", "")
        base_url = config.get("base_url", "https://api.openai.com/v1").rstrip("/")
        model = config.get("model", "dall-e-3")
        size = config.get("size", "1024x1024")

        if not api_key:
            return {"urls": [], "prompt": prompt, "status": "error", "error": "未配置 API Key"}

        # 1. Prompt 增强
        enhanced = await self._enhance_prompt(prompt, image_type)

        # 2. 调用 API
        url = f"{base_url}/images/generations"
        payload = {
            "model": model,
            "prompt": enhanced,
            "n": min(max(count, 1), 4),
            "size": size,
            "response_format": "url",
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                # 先记录原始响应，便于排查非 JSON 返回
                raw_text = resp.text
                try:
                    data = resp.json()
                except Exception:
                    preview = raw_text[:300].replace("\n", " ")
                    return {
                        "urls": [],
                        "prompt": enhanced,
                        "status": "error",
                        "error": f"API 返回非 JSON 数据（HTTP {resp.status_code}）: {preview}",
                    }

                if resp.status_code != 200:
                    err = data.get("error", {})
                    msg = err.get("message", f"API 错误: HTTP {resp.status_code}")
                    # 如果是因为"不是图像模型"被拒，尝试 fallback 到 chat completions
                    if self._is_not_image_model_error(msg):
                        return await self._generate_via_chat(
                            enhanced, config, count
                        )
                    return {"urls": [], "prompt": enhanced, "status": "error", "error": msg}

                urls = [item["url"] for item in data.get("data", []) if item.get("url")]
                if not urls:
                    return {"urls": [], "prompt": enhanced, "status": "error", "error": "未返回图片 URL"}

                return {"urls": urls, "prompt": enhanced, "status": "success"}

        except httpx.TimeoutException:
            return {"urls": [], "prompt": enhanced, "status": "error", "error": "生成超时，请稍后重试"}
        except Exception as e:
            return {"urls": [], "prompt": enhanced, "status": "error", "error": f"请求异常: {str(e)}"}

    def _is_not_image_model_error(self, msg: str) -> bool:
        """判断错误是否因为模型不是图像模型（如 GPT-5.5 被拒）。"""
        if not msg:
            return False
        keywords = [
            "需要图像模型",
            "image model",
            "not an image model",
            "not a valid image model",
            "不支持图像生成",
            "does not support image generation",
        ]
        lowered = msg.lower()
        return any(kw in lowered for kw in keywords)

    async def _generate_via_chat(
        self,
        prompt: str,
        config: dict,
        count: int = 1,
    ) -> dict:
        """Fallback：通过 chat/completions 接口生成图片。

        适用于某些模型（如 GPT-5.5）不支持 /images/generations，
        但能在 chat 接口中返回图片 URL 或 base64 的场景。
        """
        api_key = config.get("api_key", "")
        base_url = config.get("base_url", "https://api.openai.com/v1").rstrip("/")
        model = config.get("model", "gpt-4o")

        url = f"{base_url}/chat/completions"
        system_msg = (
            "You are an AI image generation assistant. "
            "Based on the user's description, generate a high-quality image "
            "and return it using markdown image syntax: ![description](url). "
            "If the image is returned as base64, use ![description](data:image/png;base64,...). "
            "Output ONLY the markdown image tag, no extra explanation."
        )
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"Generate an image: {prompt}"},
            ],
            "temperature": 0.7,
            "max_tokens": 2048,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                try:
                    data = resp.json()
                except Exception:
                    return {
                        "urls": [],
                        "prompt": prompt,
                        "status": "error",
                        "error": f"Chat 接口返回非 JSON（HTTP {resp.status_code}）",
                    }

                if resp.status_code != 200:
                    err = data.get("error", {})
                    msg = err.get("message", f"Chat 接口错误: HTTP {resp.status_code}")
                    return {"urls": [], "prompt": prompt, "status": "error", "error": msg}

                content = ""
                choices = data.get("choices", [])
                if choices:
                    message = choices[0].get("message", {})
                    # 处理可能的数组格式 content（GPT-4o 原生图片返回）
                    raw_content = message.get("content", "")
                    if isinstance(raw_content, list):
                        for part in raw_content:
                            if isinstance(part, dict):
                                if part.get("type") == "text":
                                    content += part.get("text", "")
                                elif part.get("type") == "image_url":
                                    img_url = part.get("image_url", {}).get("url", "")
                                    if img_url:
                                        return {
                                            "urls": [img_url],
                                            "prompt": prompt,
                                            "status": "success",
                                        }
                    else:
                        content = str(raw_content)

                # 从文本中提取 markdown 图片链接
                import re
                urls = re.findall(r"!\[.*?\]\((https?://[^\s)]+)\)", content)
                # 也尝试提取 base64 图片
                b64_urls = re.findall(r"!\[.*?\]\((data:image/[^\s)]+)\)", content)
                urls.extend(b64_urls)

                if not urls:
                    return {
                        "urls": [],
                        "prompt": prompt,
                        "status": "error",
                        "error": "Chat 接口未返回图片链接，该模型可能不支持直接生图",
                    }

                return {
                    "urls": urls[:count],
                    "prompt": prompt,
                    "status": "success",
                }

        except httpx.TimeoutException:
            return {"urls": [], "prompt": prompt, "status": "error", "error": "Chat 接口生成超时"}
        except Exception as e:
            return {"urls": [], "prompt": prompt, "status": "error", "error": f"Chat 接口请求异常: {str(e)}"}

    async def _enhance_prompt(self, prompt: str, image_type: str) -> str:
        """使用 LLM 将用户描述扩展为专业英文生图提示词。"""
        prefixes = {
            "main": (
                "Professional e-commerce product main image, clean simple background, "
                "centered composition, high quality commercial photography, soft studio lighting, "
            ),
            "detail": (
                "E-commerce product detail page image, lifestyle scene, showing product features "
                "and usage details, professional photography, natural lighting, appealing composition, "
            ),
        }
        prefix = prefixes.get(image_type, prefixes["main"])

        system_prompt = (
            "You are an expert e-commerce image prompt engineer. "
            "Translate and expand the user's Chinese product description into a concise, "
            "high-quality English image generation prompt (under 200 words). "
            "Focus on visual details, style, lighting, and composition. "
            "Output ONLY the prompt text, no extra explanation."
        )

        try:
            enhanced = await llm_client.chat(prompt, system_prompt=system_prompt, temperature=0.6, max_tokens=300)
            # 清理可能的引号和多余换行
            enhanced = enhanced.strip().strip('"').strip("'")
            return prefix + enhanced
        except Exception:
            # LLM 失败时回退到简单拼接
            return prefix + prompt


image_engine = ImageEngine()
