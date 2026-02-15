"""
OpenAI GPT-4 Vision 模型
"""

import json
from typing import Dict, Any
from .base_recognizer import BaseRecognizer


class OpenAIVisionRecognizer(BaseRecognizer):
    """OpenAI GPT-4 Vision 识别器"""
    
    DEFAULT_MODEL = "gpt-4o"
    
    def __init__(self, api_key: str = "", model: str = None):
        super().__init__(api_key)
        self.model = model or self.DEFAULT_MODEL
        
    def get_name(self) -> str:
        return "OpenAI GPT-4V"
    
    def analyze_image(self, image_path: str, prompt: str = None) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError("未配置OpenAI API Key")
        
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("请安装openai: pip install openai")
        
        if not prompt:
            prompt = """Analyze this image and return a JSON:
{
    "description": "Image description",
    "objects": ["object1"],
    "ocr_text": "Text in image"
}"""
        
        image_base64 = self.image_to_base64(image_path)
        mime_type = self.get_mime_type(image_path)
        
        client = OpenAI(api_key=self.api_key)
        
        response = client.chat.completions.create(
            model=self.model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{image_base64}"}
                    }
                ]
            }],
            max_tokens=2048
        )
        
        content = response.choices[0].message.content
        parsed = self._parse_response(content)
        parsed["raw_response"] = response.model_dump()
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
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            client.models.list()
            return True
        except:
            return False
