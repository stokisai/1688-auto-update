"""
OpenRouter API 客户端

统一的API网关，支持多种图像识别和图生图模型。
一个API Key可以同时使用图像识别和图生图功能。
"""

import json
import requests
from typing import Dict, Any, Optional, List
from .base_recognizer import BaseRecognizer


class OpenRouterClient(BaseRecognizer):
    """OpenRouter 统一API客户端"""
    
    API_URL = "https://openrouter.ai/api/v1/chat/completions"
    
    # 可用的图像识别模型
    VISION_MODELS = {
        "gemini-free": "google/gemini-2.0-flash-exp:free",
        "gemini-pro": "google/gemini-pro-vision",
        "gpt-4o": "openai/gpt-4o",
        "gpt-4o-mini": "openai/gpt-4o-mini",
        "claude-sonnet": "anthropic/claude-3.5-sonnet",
    }
    
    DEFAULT_VISION_MODEL = "gemini-free"
    
    def __init__(self, api_key: str = "", model: str = None):
        """
        初始化OpenRouter客户端
        
        Args:
            api_key: OpenRouter API Key
            model: 模型名称或别名
        """
        super().__init__(api_key)
        self.model = self._resolve_model(model) if model else self.VISION_MODELS[self.DEFAULT_VISION_MODEL]
        
    def _resolve_model(self, model: str) -> str:
        """解析模型名称"""
        if model in self.VISION_MODELS:
            return self.VISION_MODELS[model]
        return model
        
    def get_name(self) -> str:
        return "OpenRouter"
    
    def analyze_image(self, image_path: str, prompt: str = None,
                      model: str = None) -> Dict[str, Any]:
        """
        使用OpenRouter分析图片
        
        Args:
            image_path: 图片路径
            prompt: 分析提示词
            model: 使用的模型(可选)
            
        Returns:
            分析结果字典
        """
        if not self.api_key:
            raise ValueError("未配置OpenRouter API Key")
        
        model = self._resolve_model(model) if model else self.model
        
        # 默认提示词
        if not prompt:
            prompt = """Analyze this image and return a JSON object with:
{
    "description": "Detailed description of the image",
    "objects": ["list", "of", "main", "objects"],
    "ocr_text": "Any text visible in the image",
    "style": "Image style and composition",
    "product_features": "Product features if this is a product image"
}"""
        
        # 将图片转为base64
        image_base64 = self.image_to_base64(image_path)
        mime_type = self.get_mime_type(image_path)
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/1688-scraper",  # 可选
        }
        
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 2048
        }
        
        response = requests.post(self.API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        
        # 解析响应
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        parsed = self._parse_response(content)
        parsed["raw_response"] = result
        parsed["model_used"] = model
        
        return parsed
    
    def _parse_response(self, content: str) -> Dict[str, Any]:
        """解析AI响应内容"""
        result = {
            "description": "",
            "labels": [],
            "ocr_text": "",
            "objects": [],
            "style": "",
        }
        
        try:
            import re
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                parsed = json.loads(json_match.group())
                result["description"] = parsed.get("description", "")
                result["objects"] = parsed.get("objects", [])
                result["ocr_text"] = parsed.get("ocr_text", "")
                result["style"] = parsed.get("style", "")
                result["labels"] = parsed.get("objects", [])
                if parsed.get("product_features"):
                    result["product_features"] = parsed["product_features"]
        except json.JSONDecodeError:
            result["description"] = content
            
        return result
    
    def list_models(self) -> List[Dict[str, Any]]:
        """列出可用模型"""
        if not self.api_key:
            return []
            
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            response = requests.get(
                "https://openrouter.ai/api/v1/models",
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            return response.json().get("data", [])
        except:
            return []
    
    def validate_api_key(self) -> bool:
        """验证API Key"""
        if not self.api_key:
            return False
            
        try:
            models = self.list_models()
            return len(models) > 0
        except:
            return False
    
    def get_credit_balance(self) -> Optional[float]:
        """获取账户余额"""
        if not self.api_key:
            return None
            
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            response = requests.get(
                "https://openrouter.ai/api/v1/auth/key",
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            data = response.json().get("data", {})
            return data.get("limit", 0) - data.get("usage", 0)
        except:
            return None
