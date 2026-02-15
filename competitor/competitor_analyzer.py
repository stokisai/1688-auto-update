"""
竞品分析整合器

整合Google以图搜图和亚马逊抓取，生成竞品分析报告。
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict

from .google_image_search import GoogleImageSearch
from .amazon_scraper import AmazonScraper, AmazonProduct


@dataclass
class CompetitorAnalysisResult:
    """竞品分析结果"""
    source_image: str = ""
    amazon_url: str = ""
    amazon_asin: str = ""
    amazon_title: str = ""
    competitor_images: List[Dict[str, Any]] = field(default_factory=list)
    suggested_prompts: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return asdict(self)


class CompetitorAnalyzer:
    """竞品分析整合器"""
    
    def __init__(self, recognizer=None, headless: bool = True):
        """
        初始化竞品分析器
        
        Args:
            recognizer: 图像识别器实例 (可选)
            headless: 是否使用无头浏览器
        """
        self.recognizer = recognizer
        self.headless = headless
        self.google_search = GoogleImageSearch(headless=headless)
        self.amazon_scraper = AmazonScraper(headless=headless)
        
    def set_recognizer(self, recognizer):
        """设置图像识别器"""
        self.recognizer = recognizer
        
    def analyze_competitor(self, source_image: str,
                          output_dir: str = "./output/competitor") -> CompetitorAnalysisResult:
        """
        完整的竞品分析流程
        
        Args:
            source_image: 1688下载的图片路径(用于以图搜图)
            output_dir: 输出目录
            
        Returns:
            CompetitorAnalysisResult
        """
        result = CompetitorAnalysisResult(source_image=source_image)
        
        print(f"[1/5] 以图搜图搜索亚马逊竞品...")
        
        # 1. Google以图搜图
        search_results = self.google_search.search_by_image(source_image, filter_domain="amazon")
        
        if not search_results:
            print("  未找到亚马逊竞品")
            return result
            
        print(f"  找到 {len(search_results)} 个亚马逊结果")
        
        # 2. 选择第一个结果
        target = search_results[0]
        result.amazon_url = target["url"]
        result.amazon_asin = self.google_search.extract_amazon_asin(target["url"]) or ""
        
        print(f"[2/5] 抓取亚马逊商品: {result.amazon_url}")
        
        # 3. 抓取亚马逊商品
        amazon_product = self.amazon_scraper.scrape_product(result.amazon_url)
        result.amazon_title = amazon_product.title
        
        print(f"  标题: {result.amazon_title[:50]}...")
        print(f"  找到 {len(amazon_product.main_images)} 张图片")
        
        # 4. 下载竞品图片
        print(f"[3/5] 下载竞品图片...")
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        downloaded = self.amazon_scraper.download_images(
            amazon_product.main_images, output_dir
        )
        
        # 5. 分析图片并生成提示词
        print(f"[4/5] 分析竞品图片...")
        
        for i, local_path in enumerate(downloaded):
            image_info = {
                "filename": Path(local_path).name,
                "local_path": local_path,
                "type": "main" if i < 3 else "secondary",
                "analysis": {},
                "suggested_prompt": ""
            }
            
            # 如果有识别器，进行图像识别
            if self.recognizer:
                try:
                    analysis = self.recognizer.analyze_image(local_path)
                    image_info["analysis"] = {
                        "description": analysis.get("description", ""),
                        "labels": analysis.get("labels", []),
                        "ocr_text": analysis.get("ocr_text", ""),
                        "style": analysis.get("style", ""),
                    }
                    
                    # 生成提示词
                    prompt = self._generate_prompt_from_analysis(analysis)
                    image_info["suggested_prompt"] = prompt
                    result.suggested_prompts.append(prompt)
                    
                    print(f"  分析完成: {Path(local_path).name}")
                    
                except Exception as e:
                    print(f"  分析失败: {Path(local_path).name} - {e}")
            else:
                # 没有识别器，生成基础提示词
                basic_prompt = f"Professional product photo similar to {result.amazon_title}"
                image_info["suggested_prompt"] = basic_prompt
                result.suggested_prompts.append(basic_prompt)
                
            result.competitor_images.append(image_info)
            
        print(f"[5/5] 保存分析报告...")
        
        # 保存结果
        self._save_result(result, output_dir)
        
        return result
    
    def _generate_prompt_from_analysis(self, analysis: Dict[str, Any]) -> str:
        """从图像识别结果生成提示词"""
        parts = []
        
        # 使用描述
        if analysis.get("description"):
            parts.append(analysis["description"])
            
        # 使用风格
        if analysis.get("style"):
            parts.append(f"Style: {analysis['style']}")
            
        # 使用标签
        if analysis.get("labels"):
            labels = analysis["labels"][:5]
            parts.append(f"Elements: {', '.join(labels)}")
            
        if parts:
            return ". ".join(parts)
        
        return "Professional product photography, high quality, studio lighting"
    
    def _save_result(self, result: CompetitorAnalysisResult, output_dir: str):
        """保存分析结果"""
        output_path = Path(output_dir) / "competitor_analysis.json"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
            
        print(f"  保存到: {output_path}")
    
    def search_competitors(self, source_image: str) -> List[Dict]:
        """
        仅搜索竞品（不分析）
        
        Args:
            source_image: 图片路径
            
        Returns:
            搜索结果列表
        """
        return self.google_search.search_by_image(source_image, filter_domain="amazon")
    
    def analyze_amazon_url(self, amazon_url: str,
                          output_dir: str = "./output/competitor") -> CompetitorAnalysisResult:
        """
        分析指定的亚马逊链接
        
        Args:
            amazon_url: 亚马逊商品链接
            output_dir: 输出目录
            
        Returns:
            CompetitorAnalysisResult
        """
        result = CompetitorAnalysisResult(amazon_url=amazon_url)
        
        print(f"抓取亚马逊商品: {amazon_url}")
        
        amazon_product = self.amazon_scraper.scrape_product(amazon_url)
        result.amazon_title = amazon_product.title
        result.amazon_asin = amazon_product.asin
        
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        downloaded = self.amazon_scraper.download_images(
            amazon_product.main_images, output_dir
        )
        
        for i, local_path in enumerate(downloaded):
            image_info = {
                "filename": Path(local_path).name,
                "local_path": local_path,
                "type": "main" if i < 3 else "secondary",
                "analysis": {},
                "suggested_prompt": ""
            }
            
            if self.recognizer:
                try:
                    analysis = self.recognizer.analyze_image(local_path)
                    image_info["analysis"] = {
                        "description": analysis.get("description", ""),
                        "labels": analysis.get("labels", []),
                    }
                    prompt = self._generate_prompt_from_analysis(analysis)
                    image_info["suggested_prompt"] = prompt
                    result.suggested_prompts.append(prompt)
                except:
                    pass
                    
            result.competitor_images.append(image_info)
            
        self._save_result(result, output_dir)
        
        return result
