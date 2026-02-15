"""
Nano Banana API 图生图客户端

基于 Google Gemini 的图生图 API。
价格: ~$0.02-0.04/张
"""

import requests
from pathlib import Path
from typing import Optional
import time


class NanoBananaClient:
    """Nano Banana 图生图客户端"""
    
    API_URL = "https://api.nanobanana.dev/v1/image/generate"
    
    def __init__(self, api_key: str = ""):
        """
        初始化客户端
        
        Args:
            api_key: Nano Banana API Key
        """
        self.api_key = api_key
        self.session = requests.Session()
        
    def image_to_image(self, source_image: str, prompt: str = None,
                       output_dir: str = "./output/generated") -> str:
        """
        图生图处理
        
        Args:
            source_image: 源图片路径
            prompt: 提示词 (可选，不传则为洗稿模式)
            output_dir: 输出目录
            
        Returns:
            生成图片的路径
        """
        if not self.api_key:
            raise ValueError("未配置Nano Banana API Key")
        
        # 确保输出目录存在
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # 读取图片
        import base64
        with open(source_image, 'rb') as f:
            image_base64 = base64.b64encode(f.read()).decode('utf-8')
        
        # 构建请求
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 获取MIME类型
        ext = Path(source_image).suffix.lower()
        mime_types = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp'}
        mime_type = mime_types.get(ext, 'image/jpeg')
        
        payload = {
            "image": f"data:{mime_type};base64,{image_base64}",
            "prompt": prompt or "",  # 空提示词为洗稿模式
        }
        
        # 发送请求
        response = self.session.post(
            self.API_URL,
            headers=headers,
            json=payload,
            timeout=120
        )
        response.raise_for_status()
        
        result = response.json()
        
        # 下载生成的图片
        generated_url = result.get("image_url") or result.get("url")
        if not generated_url:
            raise Exception("API返回中没有图片URL")
        
        # 下载图片
        img_response = self.session.get(generated_url, timeout=60)
        img_response.raise_for_status()
        
        # 保存
        output_path = Path(output_dir) / f"nano_banana_{int(time.time())}.png"
        with open(output_path, 'wb') as f:
            f.write(img_response.content)
            
        return str(output_path)
    
    def validate_api_key(self) -> bool:
        """验证API Key"""
        if not self.api_key:
            return False
        # 可以添加实际验证逻辑
        return True
