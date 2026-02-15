"""
Nano Banana 基础生成（Gemini 2.5 Flash Image）
"""

import mimetypes
import os
import time
from pathlib import Path


class NanoBananaBasicClient:
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
        prompt: str = "",
        output_dir: str = "./output/generated",
    ) -> str:
        """
        图生图：使用主图作为输入，模型 gemini-2.5-flash-image。
        """
        if not self.api_key:
            raise ValueError("未配置 GEMINI_API_KEY")

        Path(output_dir).mkdir(parents=True, exist_ok=True)
        from google.genai import types

        client = self._get_client()

        # 读源图
        with open(source_image, "rb") as f:
            image_data = f.read()

        ext = Path(source_image).suffix.lower()
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }
        mime_type = mime_types.get(ext, "image/jpeg")

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
                    output_path = Path(output_dir) / f"nano_basic_{int(time.time())}{file_extension}"
                    with open(output_path, "wb") as f:
                        f.write(data_buffer)
                    print(f"[NanoBanana] 图片已保存: {output_path}")
                    break
                elif getattr(part, "text", None):
                    print(f"[NanoBanana] 文本响应: {part.text[:120]}...")
            if output_path:
                break

        if output_path:
            return str(output_path)

        raise Exception("Nano Banana 未返回图片")

    def generate(self, prompt: str = "", output_dir: str = "./output/generated") -> str:
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
                    output_path = Path(output_dir) / f"nano_basic_{int(time.time())}{file_extension}"
                    with open(output_path, "wb") as f:
                        f.write(data_buffer)
                    print(f"[NanoBanana] 图片已保存: {output_path}")
                    break
                elif getattr(part, "text", None):
                    print(f"[NanoBanana] 文本响应: {part.text[:120]}...")
            if output_path:
                break

        if output_path:
            return str(output_path)
        raise Exception("Nano Banana 未返回图片")
