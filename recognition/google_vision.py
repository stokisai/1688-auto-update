"""
Google Cloud Vision API
"""

import json
from typing import Dict, Any, List
from .base_recognizer import BaseRecognizer


class GoogleVisionRecognizer(BaseRecognizer):
    """Google Cloud Vision 识别器"""
    
    def __init__(self, credentials_path: str = ""):
        """
        Args:
            credentials_path: Google Cloud 凭证JSON文件路径
        """
        super().__init__("")
        self.credentials_path = credentials_path
        
    def get_name(self) -> str:
        return "Google Cloud Vision"
    
    def analyze_image(self, image_path: str, prompt: str = None) -> Dict[str, Any]:
        if not self.credentials_path:
            raise ValueError("未配置Google Cloud凭证")
        
        try:
            import os
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.credentials_path
            from google.cloud import vision
        except ImportError:
            raise ImportError("请安装: pip install google-cloud-vision")
        
        client = vision.ImageAnnotatorClient()
        
        with open(image_path, 'rb') as f:
            content = f.read()
        
        image = vision.Image(content=content)
        
        # 执行多种检测
        label_response = client.label_detection(image=image)
        text_response = client.text_detection(image=image)
        object_response = client.object_localization(image=image)
        
        # 处理结果
        labels = [label.description for label in label_response.label_annotations]
        
        texts = []
        for text in text_response.text_annotations[:1]:  # 只取第一个(全文)
            texts.append(text.description)
        
        objects = [obj.name for obj in object_response.localized_object_annotations]
        
        return {
            "description": ", ".join(labels[:5]),
            "labels": labels,
            "ocr_text": texts[0] if texts else "",
            "objects": objects,
            "raw_response": {
                "labels": [{"description": l.description, "score": l.score} 
                          for l in label_response.label_annotations],
                "objects": [{"name": o.name, "score": o.score}
                           for o in object_response.localized_object_annotations],
            }
        }
    
    def validate_api_key(self) -> bool:
        if not self.credentials_path:
            return False
        try:
            import os
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.credentials_path
            from google.cloud import vision
            client = vision.ImageAnnotatorClient()
            return True
        except:
            return False
