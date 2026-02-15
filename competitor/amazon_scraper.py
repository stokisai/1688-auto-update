"""
亚马逊商品抓取器

抓取亚马逊商品页面的图片和信息。
"""

import re
import time
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import requests


@dataclass
class AmazonProduct:
    """亚马逊商品数据"""
    url: str = ""
    asin: str = ""
    title: str = ""
    main_images: List[str] = field(default_factory=list)
    detail_images: List[str] = field(default_factory=list)
    description: str = ""
    bullet_points: List[str] = field(default_factory=list)
    price: str = ""


class AmazonScraper:
    """亚马逊商品抓取器"""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.driver = None
        
    def _init_driver(self):
        """初始化浏览器"""
        options = Options()
        
        if self.headless:
            options.add_argument("--headless=new")
        
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        
        self.driver = webdriver.Chrome(options=options)
        
    def _close_driver(self):
        if self.driver:
            self.driver.quit()
            self.driver = None
            
    def scrape_product(self, url: str) -> AmazonProduct:
        """
        抓取亚马逊商品信息
        
        Args:
            url: 亚马逊商品链接
            
        Returns:
            AmazonProduct 对象
        """
        product = AmazonProduct(url=url)
        
        # 提取ASIN
        asin_match = re.search(r'/dp/([A-Z0-9]{10})', url)
        if asin_match:
            product.asin = asin_match.group(1)
            
        try:
            self._init_driver()
            self.driver.get(url)
            time.sleep(3)
            
            soup = BeautifulSoup(self.driver.page_source, 'lxml')
            
            # 提取标题
            title_elem = soup.select_one("#productTitle")
            if title_elem:
                product.title = title_elem.get_text(strip=True)
            
            # 提取主图
            product.main_images = self._extract_main_images(soup)
            
            # 提取要点
            bullets = soup.select("#feature-bullets li")
            product.bullet_points = [b.get_text(strip=True) for b in bullets if b.get_text(strip=True)]
            
            # 提取描述
            desc_elem = soup.select_one("#productDescription")
            if desc_elem:
                product.description = desc_elem.get_text(strip=True)
                
            # 提取价格
            price_elem = soup.select_one(".a-price .a-offscreen")
            if price_elem:
                product.price = price_elem.get_text(strip=True)
                
        except Exception as e:
            print(f"抓取亚马逊商品失败: {e}")
        finally:
            self._close_driver()
            
        return product
    
    def _extract_main_images(self, soup: BeautifulSoup) -> List[str]:
        """提取主图"""
        images = []
        
        # 方法1: 从图片gallery提取
        gallery = soup.select("#altImages img, #imageBlock img")
        for img in gallery:
            src = img.get("src") or img.get("data-old-hires") or ""
            if src:
                # 获取大图URL
                large_src = self._get_large_image(src)
                if large_src and large_src not in images:
                    images.append(large_src)
                    
        # 方法2: 从脚本中提取
        scripts = soup.find_all("script")
        for script in scripts:
            if script.string and "colorImages" in script.string:
                urls = re.findall(r'"large":"(https://[^"]+)"', script.string)
                for url in urls:
                    if url not in images:
                        images.append(url)
                        
        return images[:10]
    
    def _get_large_image(self, url: str) -> str:
        """获取大图URL"""
        # 亚马逊图片URL转换
        # 小图: ._AC_US40_.jpg
        # 大图: ._AC_SL1500_.jpg
        url = re.sub(r'\._[A-Z]{2}_[A-Z]{2}\d+_\.', '._AC_SL1500_.', url)
        url = re.sub(r'\._[A-Z]{2}_[A-Z]{2}\d+_', '._AC_SL1500_.', url)
        return url
    
    def download_images(self, image_urls: List[str], 
                        output_dir: str = "./output/competitor") -> List[str]:
        """
        下载竞品图片
        
        Args:
            image_urls: 图片URL列表
            output_dir: 输出目录
            
        Returns:
            本地文件路径列表
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        
        downloaded = []
        
        for i, url in enumerate(image_urls):
            try:
                response = session.get(url, timeout=30)
                response.raise_for_status()
                
                ext = ".jpg"
                if ".png" in url.lower():
                    ext = ".png"
                    
                local_path = Path(output_dir) / f"competitor_{i+1:03d}{ext}"
                
                with open(local_path, 'wb') as f:
                    f.write(response.content)
                    
                downloaded.append(str(local_path))
                print(f"下载竞品图片: {local_path.name}")
                
            except Exception as e:
                print(f"下载失败: {url} - {e}")
                
        return downloaded
