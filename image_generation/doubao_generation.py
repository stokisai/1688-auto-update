"""
豆包 Seedream 文生图 / 图生图

通过火山引擎 Ark 平台调用 Doubao-Seedream 模型。
使用 OpenAI 兼容接口 (images.generate)。
"""

import base64
import time
from pathlib import Path
from typing import Optional


class DoubaoGenerationClient:
    """豆包 Seedream 图片生成客户端"""

    API_BASE = "https://ark.cn-beijing.volces.com/api/v3"
    DEFAULT_MODEL = "doubao-seedream-3.0-t2i"

    def __init__(self, api_key: str, model: str = None):
        self.api_key = api_key
        self.model = model or self.DEFAULT_MODEL

    def generate(self, prompt: str, output_dir: str = "./output/generated") -> str:
        """
        文生图：根据提示词生成图片

        Args:
            prompt: 图片描述
            output_dir: 输出目录

        Returns:
            生成图片的路径
        """
        if not self.api_key:
            raise ValueError("未配置豆包 API Key")

        import requests

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "prompt": prompt,
            "size": "1024x1024",
            "response_format": "b64_json",
        }

        response = requests.post(
            f"{self.API_BASE}/images/generations",
            headers=headers,
            json=payload,
            timeout=120,
        )
        response.raise_for_status()

        data = response.json()
        image_b64 = data["data"][0]["b64_json"]

        # 保存图片
        ts = int(time.time())
        output_path = Path(output_dir) / f"doubao_{ts}.png"
        with open(output_path, "wb") as f:
            f.write(base64.b64decode(image_b64))

        print(f"[豆包] 图片已保存: {output_path}")
        return str(output_path)

    def image_to_image(self, source_image: str, prompt: str = None,
                       output_dir: str = "./output/generated") -> str:
        """
        图生图：基于源图片和提示词生成新图片

        使用 chat/completions 接口，发送图片+提示词，让模型生成新图片描述，
        再调用文生图生成。

        Args:
            source_image: 源图片路径
            prompt: 提示词（可选）
            output_dir: 输出目录

        Returns:
            生成图片的路径
        """
        if not self.api_key:
            raise ValueError("未配置豆包 API Key")

        # 如果有提示词，直接用文生图
        if prompt:
            return self.generate(prompt, output_dir)

        # 没有提示词时，先用视觉模型分析源图，再生成
        import requests

        with open(source_image, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")

        ext = Path(source_image).suffix.lower()
        mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
        mime = mime_map.get(ext, "image/jpeg")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # 用视觉模型生成描述
        payload = {
            "model": "doubao-vision-pro-32k",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{img_b64}"},
                        },
                        {
                            "type": "text",
                            "text": (
                                "Please describe this product image in detail for AI image generation. "
                                "Include: subject, colors, materials, style, lighting, background. "
                                "Output only the English prompt, no explanation."
                            ),
                        },
                    ],
                }
            ],
        }

        resp = requests.post(
            f"{self.API_BASE}/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()

        desc = resp.json()["choices"][0]["message"]["content"]
        print(f"[豆包] 图片描述: {desc[:100]}...")

        return self.generate(desc, output_dir)
