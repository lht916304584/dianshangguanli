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
        # 自动修正常见多余路径：如 https://api.xxx.com/v1/images/generations -> https://api.xxx.com/v1
        if base_url.endswith("/images/generations"):
            base_url = base_url[: -len("/images/generations")]
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

                # 情况 A：异步任务模式（创建任务 -> 轮询）
                task_id = self._extract_task_id(data)
                if task_id:
                    print(f"[ImageEngine] Async task created: {task_id}")
                    return await self._poll_task(base_url, task_id, api_key, enhanced)

                if resp.status_code != 200:
                    err = data.get("error", {})
                    msg = err.get("message", f"API 错误: HTTP {resp.status_code}")
                    print(f"[ImageEngine] API error: {msg}")
                    if self._is_not_image_model_error(msg):
                        return await self._generate_via_chat(enhanced, config, count)
                    return {"urls": [], "prompt": enhanced, "status": "error", "error": msg}

                # 情况 B：标准 DALL-E 同步模式
                urls = [item["url"] for item in data.get("data", []) if item.get("url")]
                if urls:
                    print(f"[ImageEngine] Sync mode, returned {len(urls)} URLs")
                    return {"urls": urls, "prompt": enhanced, "status": "success"}

                # 仍未找到 URL
                print(f"[ImageEngine] No URLs in response: {raw_text[:300]}")
                return {"urls": [], "prompt": enhanced, "status": "error", "error": "未返回图片 URL"}

        except httpx.TimeoutException:
            return {"urls": [], "prompt": enhanced, "status": "error", "error": "生成超时，请稍后重试"}
        except Exception as e:
            return {"urls": [], "prompt": enhanced, "status": "error", "error": f"请求异常: {str(e)}"}

    async def _poll_task(
        self,
        base_url: str,
        task_id: str,
        api_key: str,
        prompt: str,
        max_retries: int = 30,
        interval: float = 2.0,
    ) -> dict:
        """轮询异步任务状态，直到完成或超时。"""
        headers = {"Authorization": f"Bearer {api_key}"}
        poll_url = f"{base_url}/tasks/{task_id}"
        print(f"[ImageEngine] Polling task: {poll_url}")

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                for attempt in range(max_retries):
                    await __import__("asyncio").sleep(interval)
                    resp = await client.get(poll_url, headers=headers)
                    raw = resp.text
                    print(f"[ImageEngine] Poll #{attempt + 1} HTTP {resp.status_code}: {raw[:300]}")
                    try:
                        data = resp.json()
                    except Exception:
                        continue

                    status = (
                        data.get("status", "").lower()
                        or data.get("state", "").lower()
                        or ""
                    )

                    # 任务完成/成功
                    if status in ("completed", "success", "done", "succeeded"):
                        urls = self._extract_urls_from_task(data)
                        print(f"[ImageEngine] Task completed, URLs: {urls}")
                        if urls:
                            return {
                                "urls": urls,
                                "prompt": prompt,
                                "status": "success",
                            }
                        return {
                            "urls": [],
                            "prompt": prompt,
                            "status": "error",
                            "error": "任务完成但未返回图片 URL",
                        }

                    # 任务失败
                    if status in ("failed", "error", "failure"):
                        err_msg = data.get("error", "") or data.get("message", "")
                        print(f"[ImageEngine] Task failed: {err_msg}")
                        return {
                            "urls": [],
                            "prompt": prompt,
                            "status": "error",
                            "error": f"任务失败: {err_msg}" if err_msg else "任务失败",
                        }

                print("[ImageEngine] Poll timeout")
                return {
                    "urls": [],
                    "prompt": prompt,
                    "status": "error",
                    "error": "任务轮询超时，请稍后到历史记录查看结果",
                }
        except Exception as e:
            print(f"[ImageEngine] Poll exception: {e}")
            return {
                "urls": [],
                "prompt": prompt,
                "status": "error",
                "error": f"轮询异常: {str(e)}",
            }

    def _extract_urls_from_task(self, data: dict) -> list:
        """从异步任务结果中提取图片 URL。"""
        urls = []

        # 供应商格式 1: {"result_data": [{"url": "..."}]}
        result_data = data.get("result_data", [])
        if isinstance(result_data, list):
            for item in result_data:
                if isinstance(item, dict) and item.get("url"):
                    urls.append(item["url"])
                elif isinstance(item, str):
                    urls.append(item)

        # 供应商格式 2: {"results": ["https://..."]}
        results = data.get("results", [])
        if isinstance(results, list):
            urls.extend([u for u in results if isinstance(u, str)])

        # 常见格式 3: {"result": {"image_url": "..."}}
        result = data.get("result", {})
        if isinstance(result, dict):
            if result.get("image_url"):
                urls.append(result["image_url"])
            if result.get("image_urls"):
                urls.extend(result["image_urls"])
            if result.get("url"):
                urls.append(result["url"])
            if result.get("urls"):
                urls.extend(result["urls"])

        # 常见格式 4: {"images": [{"url": "..."}]}
        images = data.get("images", [])
        if isinstance(images, list):
            for img in images:
                if isinstance(img, dict) and img.get("url"):
                    urls.append(img["url"])
                elif isinstance(img, str):
                    urls.append(img)

        # 常见格式 5: {"data": [{"url": "..."}]}
        for item in data.get("data", []):
            if isinstance(item, dict) and item.get("url"):
                urls.append(item["url"])

        # 常见格式 6: {"output": ["..."]}
        output = data.get("output", [])
        if isinstance(output, list):
            urls.extend([u for u in output if isinstance(u, str)])

        # 去重并保持顺序
        seen = set()
        unique = []
        for u in urls:
            if u and u not in seen:
                seen.add(u)
                unique.append(u)
        return unique

    def _extract_task_id(self, data: dict) -> str | None:
        """从响应中提取任务 ID，支持多种字段名和嵌套结构。"""
        candidates = ["task_id", "id", "taskId", "job_id", "request_id", "jobId"]
        for key in candidates:
            val = data.get(key)
            if val and isinstance(val, str):
                return val
        # 尝试嵌套结构
        for nested in ["data", "result", "task"]:
            obj = data.get(nested)
            if isinstance(obj, dict):
                for key in candidates:
                    val = obj.get(key)
                    if val and isinstance(val, str):
                        return val
        return None

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
                    preview = content[:200].replace("\n", " ") if content else "(空响应)"
                    return {
                        "urls": [],
                        "prompt": prompt,
                        "status": "error",
                        "error": f"该模型未返回图片链接。模型实际返回: {preview}",
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
