"""
Nano Banana 洗稿客户端

v1 使用 gemini-2.5-flash-image
v2 使用 gemini-3-pro-image-preview + googleSearch 工具 + 2K
"""

import mimetypes
import os
import time
from pathlib import Path


class NanoBananaWashClient:
    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self._client = None

    def _get_client(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _read_image(self, path: str):
        with open(path, "rb") as f:
            data = f.read()
        ext = Path(path).suffix.lower()
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }
        return data, mime_types.get(ext, "image/jpeg")

    def wash_v1(self, source_image: str, prompt: str = "", output_dir: str = "./output/generated") -> str:
        """Gemini 2.5 Flash Image"""
        if not self.api_key:
            raise ValueError("未配置 GEMINI_API_KEY")

        Path(output_dir).mkdir(parents=True, exist_ok=True)
        from google.genai import types

        client = self._get_client()
        image_data, mime_type = self._read_image(source_image)

        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt or ""),
                    types.Part.from_bytes(data=image_data, mime_type=mime_type),
                ],
            ),
        ]

        generate_content_config = types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        )

        output_path = None
        for chunk in client.models.generate_content_stream(
            model="gemini-2.5-flash-image",
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
                    file_extension = mimetypes.guess_extension(inline_data.mime_type) or ".png"
                    output_path = Path(output_dir) / f"nano_wash_v1_{int(time.time())}{file_extension}"
                    with open(output_path, "wb") as f:
                        f.write(data_buffer)
                    break
        if output_path:
            return str(output_path)
        raise Exception("Nano Banana 洗稿 v1 未返回图片")

    def wash_v2(self, source_image: str, prompt: str = "", output_dir: str = "./output/generated") -> str:
        """Gemini 3 Pro Image Preview + googleSearch + 2K"""
        if not self.api_key:
            raise ValueError("未配置 GEMINI_API_KEY")

        Path(output_dir).mkdir(parents=True, exist_ok=True)
        from google.genai import types

        client = self._get_client()
        image_data, mime_type = self._read_image(source_image)

        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt or ""),
                    types.Part.from_bytes(data=image_data, mime_type=mime_type),
                ],
            ),
        ]
        tools = [types.Tool(googleSearch=types.GoogleSearch())]
        generate_content_config = types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            image_config=types.ImageConfig(image_size="2K"),
            tools=tools,
        )

        output_path = None
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
                    file_extension = mimetypes.guess_extension(inline_data.mime_type) or ".png"
                    output_path = Path(output_dir) / f"nano_wash_v2_{int(time.time())}{file_extension}"
                    with open(output_path, "wb") as f:
                        f.write(data_buffer)
                    break
        if output_path:
            return str(output_path)
        raise Exception("Nano Banana 洗稿 v2 未返回图片")
