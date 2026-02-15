"""
OpenRouter 图生图客户端

通过OpenRouter使用多种图生图模型。
"""

import requests
from pathlib import Path
from typing import Optional
import time
import base64


class OpenRouterGenerationClient:
    """OpenRouter 图生图客户端"""
    
    API_URL = "https://openrouter.ai/api/v1/chat/completions"
    
    # 支持图生图的模型
    GENERATION_MODELS = {
        "gemini-pro": "google/gemini-3-pro-image",
        "flux2-max": "black-forest-labs/flux-2-max", 
        "seedream": "bytedance/seedream-4.5",
    }
    
    DEFAULT_MODEL = "gemini-pro"
    
    def __init__(self, api_key: str = "", model: str = None):
        self.api_key = api_key
        self.model = self.GENERATION_MODELS.get(model, self.GENERATION_MODELS[self.DEFAULT_MODEL])
        self.session = requests.Session()
        
    def image_to_image(self, source_image: str, prompt: str = None,
                       output_dir: str = "./output/generated") -> str:
        """
        图生图处理
        
        Args:
            source_image: 源图片路径
            prompt: 提示词
            output_dir: 输出目录
            
        Returns:
            生成图片的路径
        """
        if not self.api_key:
            raise ValueError("未配置OpenRouter API Key")
        
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # 读取图片
        with open(source_image, 'rb') as f:
            image_base64 = base64.b64encode(f.read()).decode('utf-8')
        
        ext = Path(source_image).suffix.lower()
        mime_types = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp'}
        mime_type = mime_types.get(ext, 'image/jpeg')
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        # 构建提示词
        full_prompt = prompt or "Recreate this image with the same content but in a different style"
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": full_prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{image_base64}"}
                        }
                    ]
                }
            ],
        }
        
        response = self.session.post(
            self.API_URL,
            headers=headers,
            json=payload,
            timeout=180
        )
        response.raise_for_status()
        
        result = response.json()
        
        # 获取生成的图片
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        # 如果是base64图片
        if "base64" in str(content):
            import re
            match = re.search(r'data:image/\w+;base64,([A-Za-z0-9+/=]+)', str(content))
            if match:
                img_data = base64.b64decode(match.group(1))
                output_path = Path(output_dir) / f"openrouter_{int(time.time())}.png"
                with open(output_path, 'wb') as f:
                    f.write(img_data)
                return str(output_path)
        
        # 如果是URL
        if "http" in str(content):
            import re
            match = re.search(r'https?://[^\s"\']+', str(content))
            if match:
                img_response = self.session.get(match.group(0), timeout=60)
                img_response.raise_for_status()
                output_path = Path(output_dir) / f"openrouter_{int(time.time())}.png"
                with open(output_path, 'wb') as f:
                    f.write(img_response.content)
                return str(output_path)
        
        raise Exception(f"无法解析图生图结果: {content[:200]}")
    
    def validate_api_key(self) -> bool:
        if not self.api_key:
            return False
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            response = requests.get(
                "https://openrouter.ai/api/v1/models",
                headers=headers,
                timeout=10
            )
            return response.status_code == 200
        except:
            return False
