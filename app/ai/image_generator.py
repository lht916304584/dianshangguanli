"""图片生成抽象层 — 当前仅返回提示词，后续接入专业生图模型"""

from abc import ABC, abstractmethod


class ImageGenerator(ABC):
    @abstractmethod
    async def generate(self, prompt: str, style: str = "e-commerce") -> dict:
        pass


class PromptOnlyGenerator(ImageGenerator):
    """当前实现：仅返回提示词，不生成图片"""

    async def generate(self, prompt: str, style: str = "e-commerce") -> dict:
        return {"url": None, "prompt": prompt, "status": "prompt_only"}


image_generator = PromptOnlyGenerator()
