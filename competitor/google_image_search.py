"""
Google 以图搜图

通过 Google Images 进行反向图片搜索。
"""

import os
import time
import requests
from pathlib import Path
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse, quote
import re

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


class GoogleImageSearch:
    """Google 以图搜图"""
    
    GOOGLE_LENS_URL = "https://lens.google.com/uploadbyurl?url="
    GOOGLE_IMAGES_URL = "https://images.google.com/"
    
    # 亚马逊域名列表
    AMAZON_DOMAINS = [
        "amazon.com", "amazon.co.uk", "amazon.de", "amazon.fr",
        "amazon.it", "amazon.es", "amazon.co.jp", "amazon.ca",
        "amazon.com.au", "amazon.in", "amazon.com.mx", "amazon.nl",
    ]
    
    def __init__(self, headless: bool = True):
        """
        初始化Google图片搜索
        
        Args:
            headless: 是否使用无头模式
        """
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
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        
        self.driver = webdriver.Chrome(options=options)
        
    def _close_driver(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            
    def search_by_image(self, image_path: str, 
                        filter_domain: str = "amazon") -> List[Dict]:
        """
        通过图片搜索相似图片
        
        Args:
            image_path: 本地图片路径
            filter_domain: 过滤域名关键词
            
        Returns:
            [
                {
                    "url": "https://amazon.com/dp/xxx",
                    "title": "商品标题",
                    "thumbnail": "缩略图URL",
                    "domain": "amazon.com"
                },
                ...
            ]
        """
        results = []
        
        try:
            self._init_driver()
            
            # 方法1: 使用Google Lens上传图片
            results = self._search_via_google_lens(image_path, filter_domain)
            
        except Exception as e:
            print(f"Google图片搜索出错: {e}")
        finally:
            self._close_driver()
            
        return results
    
    def _search_via_google_lens(self, image_path: str, 
                                 filter_domain: str) -> List[Dict]:
        """使用Google Lens搜索"""
        results = []
        
        # 访问Google Images
        self.driver.get("https://images.google.com/")
        time.sleep(2)
        
        # 查找相机图标并点击
        try:
            camera_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "[aria-label*='Search by image'], [data-ved]"))
            )
            camera_btn.click()
            time.sleep(1)
        except:
            pass
        
        # 上传图片
        try:
            # 查找上传文件输入框
            file_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
            )
            
            # 上传图片
            abs_path = str(Path(image_path).absolute())
            file_input.send_keys(abs_path)
            
            # 等待搜索结果
            time.sleep(5)
            
            # 等待页面加载
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            time.sleep(3)
            
            # 滚动加载更多结果
            self._scroll_page()
            
            # 获取搜索结果
            results = self._extract_results(filter_domain)
            
        except Exception as e:
            print(f"图片上传失败: {e}")
            
        return results
    
    def _scroll_page(self):
        """滚动页面加载更多"""
        for _ in range(3):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
        self.driver.execute_script("window.scrollTo(0, 0);")
        
    def _extract_results(self, filter_domain: str) -> List[Dict]:
        """提取搜索结果"""
        results = []
        
        # 获取所有链接
        links = self.driver.find_elements(By.TAG_NAME, "a")
        
        seen_urls = set()
        
        for link in links:
            try:
                href = link.get_attribute("href")
                if not href:
                    continue
                    
                # 检查是否匹配目标域名
                if not self._is_target_domain(href, filter_domain):
                    continue
                    
                # 解析URL
                parsed = urlparse(href)
                domain = parsed.netloc.replace("www.", "")
                
                # 去重
                if href in seen_urls:
                    continue
                seen_urls.add(href)
                
                # 提取标题
                title = link.get_attribute("title") or link.text or ""
                
                # 提取缩略图
                thumbnail = ""
                img = link.find_elements(By.TAG_NAME, "img")
                if img:
                    thumbnail = img[0].get_attribute("src") or ""
                    
                results.append({
                    "url": href,
                    "title": title[:100] if title else "",
                    "thumbnail": thumbnail,
                    "domain": domain
                })
                
            except:
                continue
                
        return results
    
    def _is_target_domain(self, url: str, filter_keyword: str) -> bool:
        """检查URL是否匹配目标域名"""
        if not url or not filter_keyword:
            return True
            
        url_lower = url.lower()
        
        if filter_keyword.lower() == "amazon":
            return any(domain in url_lower for domain in self.AMAZON_DOMAINS)
        
        return filter_keyword.lower() in url_lower
    
    def filter_amazon_results(self, results: List[Dict]) -> List[Dict]:
        """筛选亚马逊结果"""
        return [r for r in results if any(d in r.get("url", "").lower() 
                                          for d in self.AMAZON_DOMAINS)]
    
    def extract_amazon_asin(self, url: str) -> Optional[str]:
        """从亚马逊URL提取ASIN"""
        patterns = [
            r'/dp/([A-Z0-9]{10})',
            r'/gp/product/([A-Z0-9]{10})',
            r'/ASIN/([A-Z0-9]{10})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
