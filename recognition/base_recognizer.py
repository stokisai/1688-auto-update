"""
图像识别器基类

定义所有图像识别器的抽象接口。
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, List
import base64


class BaseRecognizer(ABC):
    """图像识别器基类"""
    
    def __init__(self, api_key: str = ""):
        """
        初始化识别器
        
        Args:
            api_key: API密钥
        """
        self.api_key = api_key
        
    @abstractmethod
    def analyze_image(self, image_path: str, prompt: str = None) -> Dict[str, Any]:
        """
        分析图片
        
        Args:
            image_path: 图片路径
            prompt: 可选的分析提示词
            
        Returns:
            {
                "description": "图片描述",
                "labels": ["标签1", "标签2"],
                "ocr_text": "识别出的文字",
                "objects": ["物体1", "物体2"],
                "raw_response": {...}
            }
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """获取识别器名称"""
        pass
    
    def image_to_base64(self, image_path: str) -> str:
        """
        将图片转换为base64编码
        
        Args:
            image_path: 图片路径
            
        Returns:
            base64编码字符串
        """
        with open(image_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    
    def get_mime_type(self, image_path: str) -> str:
        """
        获取图片MIME类型
        
        Args:
            image_path: 图片路径
            
        Returns:
            MIME类型字符串
        """
        ext = Path(image_path).suffix.lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.bmp': 'image/bmp',
        }
        return mime_types.get(ext, 'image/jpeg')
    
    def batch_analyze(self, image_paths: List[str], prompt: str = None) -> List[Dict[str, Any]]:
        """
        批量分析图片
        
        Args:
            image_paths: 图片路径列表
            prompt: 可选的分析提示词
            
        Returns:
            分析结果列表
        """
        results = []
        for path in image_paths:
            try:
                result = self.analyze_image(path, prompt)
                result['image_path'] = path
                result['success'] = True
                results.append(result)
            except Exception as e:
                results.append({
                    'image_path': path,
                    'success': False,
                    'error': str(e)
                })
        return results
    
    def validate_api_key(self) -> bool:
        """
        验证API Key是否有效
        
        Returns:
            是否有效
        """
        return bool(self.api_key)
