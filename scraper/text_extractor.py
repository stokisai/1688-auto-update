"""
文案提取器

提取和格式化产品文案，保存为JSON和TXT格式。
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict


@dataclass
class ProductCopywriting:
    """产品文案数据结构"""
    title: str = ""
    description: str = ""
    price_range: str = ""
    specifications: Dict[str, str] = None
    shop_name: str = ""
    
    # 图像识别结果 (可选)
    image_analysis: List[Dict[str, Any]] = None
    
    # 竞品分析结果 (可选)
    competitor_analysis: Dict[str, Any] = None
    
    # 整合后的文案
    combined_copywriting: str = ""
    
    def __post_init__(self):
        if self.specifications is None:
            self.specifications = {}
        if self.image_analysis is None:
            self.image_analysis = []
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)


class TextExtractor:
    """文案提取器"""
    
    def __init__(self, output_dir: str = "./output"):
        """
        初始化提取器
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.copywriting: Optional[ProductCopywriting] = None
        
    def from_product_data(self, product_data: Dict[str, Any]) -> ProductCopywriting:
        """
        从商品数据贴建文案对象
        
        Args:
            product_data: 商品数据字典
            
        Returns:
            ProductCopywriting 对象
        """
        self.copywriting = ProductCopywriting(
            title=product_data.get("title", ""),
            description=product_data.get("description", ""),
            price_range=product_data.get("price_range", ""),
            specifications=product_data.get("specifications", {}),
            shop_name=product_data.get("shop_name", ""),
        )
        
        # 生成初始整合文案
        self._generate_combined_copywriting()
        
        return self.copywriting
    
    def add_image_analysis(self, image_path: str, analysis_result: Dict[str, Any]):
        """
        添加图像识别结果
        
        Args:
            image_path: 图片路径
            analysis_result: 识别结果
        """
        if self.copywriting is None:
            self.copywriting = ProductCopywriting()
            
        self.copywriting.image_analysis.append({
            "image_path": image_path,
            "filename": Path(image_path).name,
            **analysis_result
        })
        
        # 更新整合文案
        self._generate_combined_copywriting()
        
    def add_competitor_analysis(self, competitor_data: Dict[str, Any]):
        """
        添加竞品分析结果
        
        Args:
            competitor_data: 竞品分析数据
        """
        if self.copywriting is None:
            self.copywriting = ProductCopywriting()
            
        self.copywriting.competitor_analysis = competitor_data
        
    def _generate_combined_copywriting(self):
        """生成整合后的文案"""
        if self.copywriting is None:
            return
            
        parts = []
        
        # 标题
        if self.copywriting.title:
            parts.append(f"【产品标题】\n{self.copywriting.title}\n")
            
        # 价格
        if self.copywriting.price_range:
            parts.append(f"【价格区间】\n{self.copywriting.price_range}\n")
            
        # 描述
        if self.copywriting.description:
            parts.append(f"【产品描述】\n{self.copywriting.description}\n")
            
        # 规格参数
        if self.copywriting.specifications:
            specs_text = "\n".join([f"  - {k}: {v}" for k, v in self.copywriting.specifications.items()])
            parts.append(f"【规格参数】\n{specs_text}\n")
            
        # 图像识别结果
        if self.copywriting.image_analysis:
            analysis_parts = []
            for item in self.copywriting.image_analysis:
                img_text = f"  图片: {item.get('filename', 'unknown')}"
                if item.get('description'):
                    img_text += f"\n    描述: {item['description']}"
                if item.get('labels'):
                    img_text += f"\n    标签: {', '.join(item['labels'])}"
                if item.get('ocr_text'):
                    img_text += f"\n    文字: {item['ocr_text']}"
                analysis_parts.append(img_text)
            parts.append(f"【图像识别结果】\n" + "\n".join(analysis_parts) + "\n")
            
        self.copywriting.combined_copywriting = "\n".join(parts)
        
    def save_json(self, filename: str = "product_info.json") -> str:
        """
        保存为JSON格式
        
        Args:
            filename: 文件名
            
        Returns:
            保存的文件路径
        """
        if self.copywriting is None:
            raise ValueError("没有可保存的文案数据")
            
        output_path = self.output_dir / filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.copywriting.to_dict(), f, ensure_ascii=False, indent=2)
            
        return str(output_path)
    
    def save_txt(self, filename: str = "product_info.txt") -> str:
        """
        保存为TXT格式
        
        Args:
            filename: 文件名
            
        Returns:
            保存的文件路径
        """
        if self.copywriting is None:
            raise ValueError("没有可保存的文案数据")
            
        output_path = self.output_dir / filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(self.copywriting.combined_copywriting)
            
        return str(output_path)
    
    def save_all(self) -> Dict[str, str]:
        """
        保存所有格式
        
        Returns:
            {格式: 路径} 字典
        """
        return {
            "json": self.save_json(),
            "txt": self.save_txt(),
        }
        
    def load_json(self, filename: str = "product_info.json") -> ProductCopywriting:
        """
        从JSON文件加载
        
        Args:
            filename: 文件名
            
        Returns:
            ProductCopywriting 对象
        """
        input_path = self.output_dir / filename
        
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        self.copywriting = ProductCopywriting(**data)
        return self.copywriting
    
    def get_prompt_text(self, language: str = "en") -> str:
        """
        获取用于图生图的提示词文本
        
        Args:
            language: 语言 ("en" 或 "zh")
            
        Returns:
            提示词文本
        """
        if self.copywriting is None:
            return ""
            
        # 收集关键信息
        keywords = []
        
        # 从标题提取
        if self.copywriting.title:
            keywords.append(self.copywriting.title)
            
        # 从规格参数提取
        for key, value in self.copywriting.specifications.items():
            keywords.append(f"{key}: {value}")
            
        # 从图像识别结果提取
        for item in self.copywriting.image_analysis:
            if item.get('labels'):
                keywords.extend(item['labels'])
            if item.get('description'):
                keywords.append(item['description'])
                
        # 生成提示词
        if language == "en":
            # 简单的中文转英文提示（实际应用中可能需要翻译API）
            return ", ".join(set(keywords))
        else:
            return "，".join(set(keywords))
