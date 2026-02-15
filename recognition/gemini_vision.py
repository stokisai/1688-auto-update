"""
Google Gemini 视觉模型
"""

import json
import requests
from typing import Dict, Any
from .base_recognizer import BaseRecognizer


class GeminiVisionRecognizer(BaseRecognizer):
    """Google Gemini 视觉识别器"""
    
    API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    DEFAULT_MODEL = "gemini-1.5-flash"
    
    def __init__(self, api_key: str = "", model: str = None):
        super().__init__(api_key)
        self.model = model or self.DEFAULT_MODEL
        
    def get_name(self) -> str:
        return "Google Gemini"
    
    def analyze_image(self, image_path: str, prompt: str = None) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError("未配置Gemini API Key")
        
        if not prompt:
            prompt = """Analyze this image and return a JSON object:
{
    "description": "Image description",
    "objects": ["object1", "object2"],
    "ocr_text": "Text in image",
    "style": "Image style"
}"""
        
        image_base64 = self.image_to_base64(image_path)
        mime_type = self.get_mime_type(image_path)
        
        url = self.API_URL.format(model=self.model) + f"?key={self.api_key}"
        
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": image_base64
                        }
                    }
                ]
            }]
        }
        
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        content = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        
        parsed = self._parse_response(content)
        parsed["raw_response"] = result
        return parsed
    
    def _parse_response(self, content: str) -> Dict[str, Any]:
        result = {"description": "", "labels": [], "ocr_text": "", "objects": []}
        try:
            import re
            match = re.search(r'\{[\s\S]*\}', content)
            if match:
                parsed = json.loads(match.group())
                result.update({
                    "description": parsed.get("description", ""),
                    "objects": parsed.get("objects", []),
                    "labels": parsed.get("objects", []),
                    "ocr_text": parsed.get("ocr_text", ""),
                })
        except:
            result["description"] = content
        return result
    
    def validate_api_key(self) -> bool:
        if not self.api_key:
            return False
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}"
            r = requests.get(url, timeout=10)
            return r.status_code == 200
        except:
            return False
