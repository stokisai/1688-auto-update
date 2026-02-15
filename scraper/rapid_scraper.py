"""
RapidAPI 1688 商品抓取器

使用 RapidAPI 上的 1688 API 进行抓取。
注意: 需要用户补侧 API Key 和具体接口配置。
"""

import re
import json
import requests
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from .html_parser import ProductData


class RapidApiScraper:
    """使用 RapidAPI 抓取 1688 商品"""
    
    # RapidAPI 端点 - 待配置
    # 常见的 1688 API: https://rapidapi.com/search/1688
    RAPID_API_HOST = ""  # 待填写, 例如: "1688-product-scraper.p.rapidapi.com"
    RAPID_API_URL = ""   # 待填写, 例如: "https://1688-product-scraper.p.rapidapi.com/product"
    
    def __init__(self, api_key: str = ""):
        """
        初始化 RapidAPI 抓取器
        
        Args:
            api_key: RapidAPI API Key (从 RapidAPI 获取)
        """
        self.api_key = api_key
        self.product_data: Optional[ProductData] = None
        
        if not self.api_key:
            print("[RapidAPI] ⚠️ 警告: 未配置 API Key")
        
    def is_configured(self) -> bool:
        """检查是否已配置"""
        return bool(self.api_key and self.RAPID_API_HOST and self.RAPID_API_URL)
        
    def scrape_product(self, url: str) -> ProductData:
        """
        抓取商品信息
        
        Args:
            url: 1688商品链接
            
        Returns:
            ProductData 对象
        """
        self.product_data = ProductData(url=url)
        
        if not self.is_configured():
            print("[RapidAPI] ⚠️ 未配置 RapidAPI，请先配置 API Key 和端点")
            print("[RapidAPI] 请在配置页面填写 RapidAPI 相关配置")
            raise ValueError("RapidAPI 未配置，请先配置 API Key")
        
        print(f"[RapidAPI] 正在抓取: {url}")
        
        try:
            # 提取商品ID
            product_id = self._extract_product_id(url)
            
            if not product_id:
                raise ValueError("无法从URL提取商品ID")
            
            # 调用 RapidAPI
            headers = {
                'X-RapidAPI-Key': self.api_key,
                'X-RapidAPI-Host': self.RAPID_API_HOST,
            }
            
            params = {
                'url': url,
                # 或者使用 product_id
                # 'product_id': product_id,
            }
            
            response = requests.get(self.RAPID_API_URL, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                self._parse_response(data)
                print(f"[RapidAPI] ✓ 抓取成功")
            else:
                print(f"[RapidAPI] API 请求失败: {response.status_code}")
                raise ValueError(f"API 请求失败: {response.status_code}")
                
        except Exception as e:
            print(f"[RapidAPI] 抓取出错: {e}")
            raise
            
        return self.product_data
    
    def _parse_response(self, data: dict):
        """
        解析 API 响应
        
        注意: 具体字段需要根据实际使用的 RapidAPI 接口调整
        """
        # 以下是常见的字段映射，需要根据实际 API 响应调整
        self.product_data.title = data.get('title') or data.get('name') or ''
        self.product_data.description = data.get('description') or ''
        self.product_data.price_range = data.get('price') or data.get('price_range') or ''
        self.product_data.shop_name = data.get('shop_name') or data.get('seller') or ''
        
        # 图片
        images = data.get('images') or data.get('main_images') or []
        if isinstance(images, list):
            self.product_data.main_images = images
        
        detail_images = data.get('detail_images') or data.get('description_images') or []
        if isinstance(detail_images, list):
            self.product_data.detail_images = detail_images
        
        # 规格
        specs = data.get('specifications') or data.get('attributes') or {}
        if isinstance(specs, dict):
            self.product_data.specifications = specs
    
    def _extract_product_id(self, url: str) -> Optional[str]:
        """从URL提取商品ID"""
        # 1688 URL 格式: https://detail.1688.com/offer/123456789.html
        match = re.search(r'/offer/(\d+)\.html', url)
        if match:
            return match.group(1)
        return None
    
    def get_main_images(self) -> List[str]:
        """获取主图URL列表"""
        return self.product_data.main_images if self.product_data else []
    
    def get_detail_images(self) -> List[str]:
        """获取详情页图片URL列表"""
        return self.product_data.detail_images if self.product_data else []
    
    def get_product_text(self) -> Dict[str, Any]:
        """获取所有文案信息"""
        if not self.product_data:
            return {}
        return {
            "title": self.product_data.title,
            "description": self.product_data.description,
            "price_range": self.product_data.price_range,
            "specifications": self.product_data.specifications,
            "shop_name": self.product_data.shop_name,
        }


# ============================================================
# 配置说明
# ============================================================
"""
如何配置 RapidAPI 1688 抓取器:

1. 访问 https://rapidapi.com/search/1688 搜索可用的 1688 API

2. 选择一个 API 并订阅 (很多有免费额度)

3. 获取 API Key (在 RapidAPI 控制台)

4. 修改以下配置:
   - RAPID_API_HOST: API 的 host，例如 "1688-scraper.p.rapidapi.com"
   - RAPID_API_URL: API 的完整 URL
   
5. 根据 API 文档调整 _parse_response() 方法的字段映射

推荐的 RapidAPI 1688 API:
- Scraper 1688: https://rapidapi.com/xxx/api/scraper-1688
- 1688 Product API: https://rapidapi.com/xxx/api/1688-product-api
"""


if __name__ == "__main__":
    print("=" * 60)
    print("RapidAPI 1688 抓取器 - 配置说明")
    print("=" * 60)
    print(__doc__)
