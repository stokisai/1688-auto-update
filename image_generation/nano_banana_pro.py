"""
Nano Banana Pro (替换为 Gemini 图生图模板)

按用户提供的官方示例，通过 Google Gemini API 以 2K 分辨率生成图片。
"""

import mimetypes
import os
import time
from pathlib import Path
from typing import Optional


class NanoBananaProClient:
    """使用 Gemini API 生成图片（流式）。"""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self._client = None

    def _get_client(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def image_to_image(
        self,
        source_image: str,
        prompt: str = None,
        output_dir: str = "./output/generated",
    ) -> str:
        """
        按示例调用 Gemini 生成图片，默认 2K。
        """
        if not self.api_key:
            raise ValueError("未配置 GEMINI_API_KEY")

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        from google.genai import types

        client = self._get_client()

        # 读入源图
        with open(source_image, "rb") as f:
            image_data = f.read()

        # MIME 推断
        ext = Path(source_image).suffix.lower()
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }
        mime_type = mime_types.get(ext, "image/jpeg")

        model = "gemini-3-pro-image-preview"

        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt or ""),
                    types.Part.from_bytes(data=image_data, mime_type=mime_type),
                ],
            )
        ]

        tools = [types.Tool(googleSearch=types.GoogleSearch())]

        generate_content_config = types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            image_config=types.ImageConfig(image_size="2K"),
            tools=tools,
        )

        output_path: Optional[Path] = None
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config,
        ):
            if (
                not chunk.candidates
                or not chunk.candidates[0].content
                or not chunk.candidates[0].content.parts
            ):
                continue

            for part in chunk.candidates[0].content.parts:
                if getattr(part, "inline_data", None) and part.inline_data.data:
                    inline_data = part.inline_data
                    data_buffer = inline_data.data
                    file_extension = (
                        mimetypes.guess_extension(inline_data.mime_type) or ".png"
                    )
                    output_path = Path(output_dir) / f"nano_banana_pro_{int(time.time())}{file_extension}"
                    with open(output_path, "wb") as f:
                        f.write(data_buffer)
                    print(f"[NanoBananaPro] 图片已保存: {output_path}")
                    break
                elif getattr(part, "text", None):
                    print(f"[NanoBananaPro] 文本响应: {part.text[:120]}...")

            if output_path:
                break

        if output_path:
            return str(output_path)

        raise Exception("Nano Banana Pro (Gemini) 未返回图片")

    def generate(self, prompt: str = "", output_dir: str = "./output/generated") -> str:
        """
        纯文生图：仅使用文字提示词生成图片。
        """
        if not self.api_key:
            raise ValueError("未配置 GEMINI_API_KEY")

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        from google.genai import types

        client = self._get_client()

        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt or "")],
            ),
        ]

        tools = [types.Tool(googleSearch=types.GoogleSearch())]

        generate_content_config = types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            image_config=types.ImageConfig(image_size="2K"),
            tools=tools,
        )

        output_path: Optional[Path] = None
        for chunk in client.models.generate_content_stream(
            model="gemini-3-pro-image-preview",
            contents=contents,
            config=generate_content_config,
        ):
            if (
                not chunk.candidates
                or not chunk.candidates[0].content
                or not chunk.candidates[0].content.parts
            ):
                continue

            for part in chunk.candidates[0].content.parts:
                if getattr(part, "inline_data", None) and part.inline_data.data:
                    inline_data = part.inline_data
                    data_buffer = inline_data.data
                    file_extension = (
                        mimetypes.guess_extension(inline_data.mime_type) or ".png"
                    )
                    output_path = Path(output_dir) / f"nano_banana_pro_{int(time.time())}{file_extension}"
                    with open(output_path, "wb") as f:
                        f.write(data_buffer)
                    print(f"[NanoBananaPro] 图片已保存: {output_path}")
                    break
                elif getattr(part, "text", None):
                    print(f"[NanoBananaPro] 文本响应: {part.text[:120]}...")

            if output_path:
                break

        if output_path:
            return str(output_path)

        raise Exception("Nano Banana Pro (Gemini) 未返回图片")
