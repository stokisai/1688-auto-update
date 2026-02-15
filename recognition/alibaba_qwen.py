"""
阿里云通义千问视觉模型

使用DashScope SDK调用通义千问VL。
价格: ¥0.0015/千token (最低价格)
"""

import json
from typing import Dict, Any, Optional
from .base_recognizer import BaseRecognizer


class QwenVLRecognizer(BaseRecognizer):
    """通义千问VL识别器"""
    
    DEFAULT_MODEL = "qwen-vl-plus"
    
    def __init__(self, api_key: str = "", model: str = None):
        """
        初始化通义千问识别器
        
        Args:
            api_key: 阿里云DashScope API Key
            model: 模型名称 (qwen-vl-plus 或 qwen-vl-max)
        """
        super().__init__(api_key)
        self.model = model or self.DEFAULT_MODEL
        
    def get_name(self) -> str:
        return "通义千问VL"
    
    def analyze_image(self, image_path: str, prompt: str = None) -> Dict[str, Any]:
        """
        使用通义千问分析图片
        
        Args:
            image_path: 图片路径
            prompt: 分析提示词
            
        Returns:
            分析结果字典
        """
        if not self.api_key:
            raise ValueError("未配置通义千问API Key")
        
        try:
            import dashscope
            from dashscope import MultiModalConversation
        except ImportError:
            raise ImportError("请安装dashscope: pip install dashscope")
        
        # 设置API Key
        dashscope.api_key = self.api_key
        
        # 默认提示词
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
        
        # 使用本地文件
        messages = [
            {
                "role": "user",
                "content": [
                    {"image": f"file://{image_path}"},
                    {"text": prompt}
                ]
            }
        ]
        
        # 调用API
        response = MultiModalConversation.call(
            model=self.model,
            messages=messages
        )
        
        # 检查响应
        if response.status_code != 200:
            raise Exception(f"API调用失败: {response.message}")
        
        # 获取内容
        content = response.output.choices[0].message.content[0].get("text", "")
        
        # 解析响应
        parsed = self._parse_response(content)
        parsed["raw_response"] = {
            "status_code": response.status_code,
            "request_id": response.request_id,
            "usage": response.usage.__dict__ if response.usage else {}
        }
        
        return parsed
    
    def _parse_response(self, content: str) -> Dict[str, Any]:
        """解析AI响应内容"""
        result = {
            "description": "",
            "labels": [],
            "ocr_text": "",
            "objects": [],
        }
        
        try:
            import re
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
        """验证API Key"""
        if not self.api_key:
            return False
            
        try:
            import dashscope
            dashscope.api_key = self.api_key
            
            # 尝试列出模型
            from dashscope import Models
            result = Models.list()
            return result.status_code == 200
        except:
            return False
