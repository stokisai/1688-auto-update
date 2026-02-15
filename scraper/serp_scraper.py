"""
SerpApi 1688 商品抓取器

使用 SerpApi 进行网页抓取，获取1688商品信息。
"""

import re
import json
import requests
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from .html_parser import ProductData


class SerpApiScraper:
    """使用 SerpApi 抓取 1688 商品"""
    
    # SerpApi 端点
    SERP_API_URL = "https://serpapi.com/search"
    
    def __init__(self, api_key: str = ""):
        """
        初始化 SerpApi 抓取器
        
        Args:
            api_key: SerpApi API Key
        """
        self.api_key = api_key or "081c24883966800829defaacc9226d81832f54fbeb82b82bda1f5c8a9d01df40"
        self.product_data: Optional[ProductData] = None
        
    def scrape_product(self, url: str) -> ProductData:
        """
        抓取商品信息
        
        Args:
            url: 1688商品链接
            
        Returns:
            ProductData 对象
        """
        self.product_data = ProductData(url=url)
        
        print(f"[SerpApi] 正在抓取: {url}")
        
        try:
            # 使用 SerpApi 的 Google 搜索来获取页面内容
            # 或者使用其 HTML 抓取功能
            
            html_content = self._fetch_page_html(url)
            
            if html_content:
                # 使用 HTML 解析器解析内容
                from .html_parser import HTMLParser
                parser = HTMLParser()
                self.product_data = parser.parse_from_html(html_content, url)
                print(f"[SerpApi] ✓ 抓取成功")
            else:
                # 从URL提取域名用于提示
                from urllib.parse import urlparse
                domain = urlparse(url).netloc or "目标网站"
                print(f"[SerpApi] ⚠️ 无法获取页面内容，{domain} 可能有反爬保护")
                print(f"[SerpApi] 建议使用 Selenium 浏览器模式")
                # 返回空数据而不是抛出异常
                
        except requests.exceptions.Timeout:
            print(f"[SerpApi] ⚠️ 请求超时，请检查网络连接")
        except requests.exceptions.RequestException as e:
            print(f"[SerpApi] ⚠️ 网络请求失败: {e}")
        except Exception as e:
            print(f"[SerpApi] 抓取出错: {e}")
            import traceback
            traceback.print_exc()
            
        return self.product_data
    
    def _fetch_page_html(self, url: str) -> Optional[str]:
        """
        使用 SerpApi 获取页面 HTML
        
        SerpApi 提供了多种方式，这里尝试使用其通用搜索功能
        """
        # 尝试使用 SerpApi 的 Google 搜索获取缓存页面
        # 或者直接使用 requests + 代理
        
        # 方法1: 直接请求 (可能被封)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://www.1688.com/',
        }
        
        try:
            print(f"[SerpApi] 尝试直接请求...")
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200 and len(response.text) > 1000:
                # 检查是否是验证码页面
                if '验证' not in response.text and 'captcha' not in response.text.lower():
                    print(f"[SerpApi] 直接请求成功")
                    return response.text
        except Exception as e:
            print(f"[SerpApi] 直接请求失败: {e}")
        
        # 方法2: 使用 SerpApi 进行搜索获取信息
        try:
            print(f"[SerpApi] 尝试通过搜索获取信息...")
            
            # 从URL提取商品ID
            product_id = self._extract_product_id(url)
            if product_id:
                # 搜索商品ID
                params = {
                    'api_key': self.api_key,
                    'engine': 'google',
                    'q': f'site:detail.1688.com {product_id}',
                    'gl': 'cn',
                    'hl': 'zh-cn',
                }
                
                response = requests.get(self.SERP_API_URL, params=params, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    
                    # 尝试从搜索结果中提取信息
                    organic_results = data.get('organic_results', [])
                    if organic_results:
                        result = organic_results[0]
                        # 从搜索结果中提取标题和描述
                        title = result.get('title', '')
                        snippet = result.get('snippet', '')
                        
                        print(f"[SerpApi] 从搜索结果获取到标题: {title}")
                        
                        # 贴建一个基础的 ProductData
                        self.product_data.title = title
                        self.product_data.description = snippet
                        
                        # 尝试获取缓存页面
                        cached_page = result.get('cached_page_link')
                        if cached_page:
                            cache_response = requests.get(cached_page, timeout=30)
                            if cache_response.status_code == 200:
                                return cache_response.text
                        
        except Exception as e:
            print(f"[SerpApi] 搜索获取失败: {e}")
        
        return None
    
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


if __name__ == "__main__":
    # 测试
    scraper = SerpApiScraper()
    url = "https://detail.1688.com/offer/123456789.html"
    print(f"测试抓取: {url}")
