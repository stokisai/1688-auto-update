"""
智谱AI GLM-4.6V 视觉理解模型

使用 OpenAI 兼容接口调用智谱 GLM-4.6V。
GLM-4.6V-Flash 完全免费。
"""

import json
import base64
import re
from typing import Dict, Any
from .base_recognizer import BaseRecognizer


class ZhipuVisionRecognizer(BaseRecognizer):
    """智谱AI GLM-4.6V 视觉识别器"""

    API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    DEFAULT_MODEL = "glm-4.6v-flash"

    def __init__(self, api_key: str = "", model: str = None):
        super().__init__(api_key)
        self.model = model or self.DEFAULT_MODEL

    def get_name(self) -> str:
        return "智谱AI GLM-4.6V"

    def analyze_image(self, image_path: str, prompt: str = None) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError("未配置智谱AI API Key")

        import requests

        # 图片转 base64
        b64 = self.image_to_base64(image_path)
        mime = self.get_mime_type(image_path)
        data_url = f"data:{mime};base64,{b64}"

        if not prompt:
            prompt = """请详细分析这张图片，返回以下信息：
1. 图片描述：详细描述图片内容
2. 主要物体：列出图片中的主要物体
3. 文字内容：识别图片中的所有文字
4. 产品特征：如果是产品图，描述产品的特点

请用JSON格式返回：
{
    "description": "图片描述",
    "objects": ["物体1", "物体2"],
    "ocr_text": "识别出的文字",
    "product_features": "产品特征"
}"""

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url},
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        response = requests.post(self.API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()

        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        parsed = self._parse_response(content)
        parsed["raw_response"] = {
            "model": data.get("model", ""),
            "usage": data.get("usage", {}),
        }

        return parsed

    def _parse_response(self, content: str) -> Dict[str, Any]:
        result = {
            "description": "",
            "labels": [],
            "ocr_text": "",
            "objects": [],
        }

        try:
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                parsed = json.loads(json_match.group())
                result["description"] = parsed.get("description", "")
                result["objects"] = parsed.get("objects", [])
                result["ocr_text"] = parsed.get("ocr_text", "")
                result["labels"] = parsed.get("objects", [])
                if parsed.get("product_features"):
                    result["product_features"] = parsed["product_features"]
        except json.JSONDecodeError:
            result["description"] = content

        return result

    def validate_api_key(self) -> bool:
        if not self.api_key:
            return False
        try:
            import requests
            resp = requests.get(
                "https://open.bigmodel.cn/api/paas/v4/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10,
            )
            return resp.status_code == 200
        except Exception:
            return False
