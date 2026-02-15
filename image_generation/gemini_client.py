# -*- coding: utf-8 -*-
"""
Gemini 图生图客户端

使用 Google Gemini API 进行图生图处理。
"""

import base64
import mimetypes
import os
from pathlib import Path
from typing import Optional
import time


class GeminiImageClient:
    """Gemini 图生图客户端"""
    
    def __init__(self, api_key: str = ""):
        """
        初始化客户端
        
        Args:
            api_key: Gemini API Key
        """
        self.api_key = api_key
        self._client = None
        
    def _get_client(self):
        """获取 Gemini 客户端"""
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client
    
    def image_to_image(self, source_image: str, prompt: str = None,
                       output_dir: str = "./output/generated") -> str:
        """
        图生图处理
        
        Args:
            source_image: 源图片路径
            prompt: 提示词 (可选，不传则为洗稿模式)
            aspect_ratio: 可选宽高比（如 "1:1" / "16:9" / "9:16"）
            image_size: 可选分辨率（如 "1K" / "2K" / "4K"）
            output_dir: 输出目录
            
        Returns:
            生成图片的路径
        """
        if not self.api_key:
            raise ValueError("未配置 Gemini API Key")
        
        # 确保输出目录存在
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        from google import genai
        from google.genai import types
        
        client = self._get_client()
        
        # 读取图片
        with open(source_image, 'rb') as f:
            image_data = f.read()
        
        # 获取MIME类型
        ext = Path(source_image).suffix.lower()
        mime_types_map = {
            '.jpg': 'image/jpeg', 
            '.jpeg': 'image/jpeg', 
            '.png': 'image/png', 
            '.webp': 'image/webp'
        }
        mime_type = mime_types_map.get(ext, 'image/jpeg')
        
        # 构建请求
        model = "gemini-3-pro-image-preview"
        
        # 默认提示词
        if not prompt:
            prompt = "请重新生成这张图片，保持产品主体不变，移除所有水印和文字"
        
        # 构建内容
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt),
                    types.Part.from_bytes(data=image_data, mime_type=mime_type),
                ],
            ),
        ]
        
        # 配置：按用户提供的官方示例，带 image_config 2K 与 googleSearch 工具
        generate_content_config = types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            image_config=types.ImageConfig(image_size="2K"),
            # 使用官方示例的 camelCase 字段名 googleSearch
            tools=[types.Tool(googleSearch=types.GoogleSearch())],
        )
        
        print(f"[Gemini] 正在调用 Gemini API...")
        print(f"[Gemini] 提示词: {prompt[:50]}...")
        
        # 生成（流式）
        output_path = None
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config,
        ):
            if (
                chunk.candidates is None
                or chunk.candidates[0].content is None
                or chunk.candidates[0].content.parts is None
            ):
                continue
            for part in chunk.candidates[0].content.parts:
                if getattr(part, "inline_data", None) and part.inline_data.data:
                    inline_data = part.inline_data
                    data_buffer = inline_data.data
                    file_extension = mimetypes.guess_extension(inline_data.mime_type) or '.png'
                    output_path = Path(output_dir) / f"gemini_{int(time.time())}{file_extension}"
                    with open(output_path, 'wb') as f:
                        f.write(data_buffer)
                    print(f"[Gemini] ✓ 图片已保存: {output_path}")
                    break
                if getattr(part, "text", None):
                    print(f"[Gemini] 文本响应: {part.text[:120]}...")
            if output_path:
                break
        
        if output_path:
            return str(output_path)
        raise Exception("Gemini API 未返回图片")
    
    def validate_api_key(self) -> bool:
        """验证API Key"""
        if not self.api_key:
            return False
        try:
            from google import genai
            client = genai.Client(api_key=self.api_key)
            # 尝试列出模型来验证
            list(client.models.list())
            return True
        except Exception as e:
            print(f"[Gemini] API Key 验证失败: {e}")
            return False
