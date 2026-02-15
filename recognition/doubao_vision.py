"""
豆包视觉理解模型

字节跳动豆包(Doubao)图像识别API。
免费额度: 50万token + 可领取5亿token
价格: ¥0.003/千token
"""

import json
import requests
from typing import Dict, Any, Optional
from .base_recognizer import BaseRecognizer


class DoubaoVisionRecognizer(BaseRecognizer):
    """豆包视觉理解模型"""
    
    # 火山引擎API端点
    API_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
    
    # 默认模型
    DEFAULT_MODEL = "doubao-vision-pro-32k"
    
    def __init__(self, api_key: str = "", model: str = None):
        """
        初始化豆包识别器
        
        Args:
            api_key: 火山引擎API Key
            model: 模型名称
        """
        super().__init__(api_key)
        self.model = model or self.DEFAULT_MODEL
        
    def get_name(self) -> str:
        return "豆包视觉理解"
    
    def analyze_image(self, image_path: str, prompt: str = None) -> Dict[str, Any]:
        """
        使用豆包分析图片
        
        Args:
            image_path: 图片路径
            prompt: 分析提示词
            
        Returns:
            分析结果字典
        """
        if not self.api_key:
            raise ValueError("未配置豆包API Key")
        
        # 默认提示词
        if not prompt:
            prompt = """请详细分析这张图片，返回以下信息：
1. 图片描述：详细描述图片内容
2. 主要物体：列出图片中的主要物体
3. 文字内容：识别图片中的所有文字
4. 产品特征：如果是产品图，描述产品的特点
5. 图片风格：描述图片的拍摄风格和背景

请用JSON格式返回，包含以下字段：
{
    "description": "图片描述",
    "objects": ["物体1", "物体2"],
    "ocr_text": "识别出的文字",
    "product_features": "产品特征",
    "style": "图片风格"
}"""
        
        # 将图片转为base64
        image_base64 = self.image_to_base64(image_path)
        mime_type = self.get_mime_type(image_path)
        
        # 构建请求
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "model": self.model,
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
        
        # 发送请求
        response = requests.post(self.API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        
        # 解析响应
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        # 尝试解析JSON
        parsed = self._parse_response(content)
        parsed["raw_response"] = result
        
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
        
        # 尝试解析JSON
        try:
            # 查找JSON块
            import re
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                parsed = json.loads(json_match.group())
                result["description"] = parsed.get("description", "")
                result["objects"] = parsed.get("objects", [])
                result["ocr_text"] = parsed.get("ocr_text", "")
                result["style"] = parsed.get("style", "")
                
                # 合并labels
                if parsed.get("objects"):
                    result["labels"] = parsed["objects"]
                if parsed.get("product_features"):
                    result["product_features"] = parsed["product_features"]
        except json.JSONDecodeError:
            # 如果无法解析JSON，使用原始文本作为描述
            result["description"] = content
            
        return result
    
    def validate_api_key(self) -> bool:
        """验证API Key"""
        if not self.api_key:
            return False
            
        try:
            # 简单的验证请求
            headers = {
                "Authorization": f"Bearer {self.api_key}"
            }
            response = requests.get(
                "https://ark.cn-beijing.volces.com/api/v3/models",
                headers=headers,
                timeout=10
            )
            return response.status_code == 200
        except:
            return False
