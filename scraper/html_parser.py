"""
1688 商品页面 HTML 解析器

纯HTML解析方式，无需浏览器驱动。
用户可以手动提供页面HTML内容进行解析。
"""

import re
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from bs4 import BeautifulSoup


@dataclass
class ProductData:
    """商品数据结构"""
    url: str = ""
    title: str = ""
    description: str = ""
    price_range: str = ""
    specifications: Dict[str, str] = field(default_factory=dict)
    main_images: List[str] = field(default_factory=list)
    detail_images: List[str] = field(default_factory=list)
    shop_name: str = ""
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "url": self.url,
            "title": self.title,
            "description": self.description,
            "price_range": self.price_range,
            "specifications": self.specifications,
            "main_images": self.main_images,
            "detail_images": self.detail_images,
            "shop_name": self.shop_name,
        }
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class HTMLParser:
    """1688 商品HTML解析器 - 纯静态解析，无需浏览器"""
    
    def __init__(self):
        self.product_data: Optional[ProductData] = None
        
    def parse_from_html(self, html_content: str, url: str = "") -> ProductData:
        """
        从HTML内容解析商品信息
        
        Args:
            html_content: 页面HTML内容
            url: 商品链接(可选)
            
        Returns:
            ProductData 对象
        """
        self.product_data = ProductData(url=url)
        
        if not html_content or len(html_content) < 100:
            raise ValueError("HTML内容太短或为空，请提供完整的页面HTML")
        
        try:
            soup = BeautifulSoup(html_content, 'lxml')
        except Exception as e:
            # 如果lxml解析失败，尝试使用html.parser
            try:
                soup = BeautifulSoup(html_content, 'html.parser')
            except Exception as e2:
                raise ValueError(f"HTML解析失败: {e2}")
        
        print("正在解析HTML内容...")
        
        # 提取各项信息
        self._extract_title(soup)
        self._extract_price(soup)
        self._extract_main_images(soup, html_content)
        self._extract_detail_images(soup)
        self._extract_specifications(soup)
        self._extract_description(soup)
        self._extract_shop_name(soup)
        
        # 打印结果摘要
        print(f"\n{'='*50}")
        print("解析结果:")
        print(f"{'='*50}")
        print(f"✓ 标题: {self.product_data.title[:80] if self.product_data.title else '未获取'}...")
        print(f"✓ 价格: {self.product_data.price_range if self.product_data.price_range else '未获取'}")
        print(f"✓ 主图: {len(self.product_data.main_images)} 张")
        print(f"✓ 副图: {len(self.product_data.detail_images)} 张")
        print(f"✓ 规格: {len(self.product_data.specifications)} 项")
        print(f"✓ 店铺: {self.product_data.shop_name if self.product_data.shop_name else '未获取'}")
        
        if not self.product_data.title and not self.product_data.main_images:
            print("\n⚠️ 警告: 未能提取到标题和图片，可能原因:")
            print("   1. HTML内容不完整")
            print("   2. 页面结构已更新，需要调整选择器")
            print("   3. HTML来自验证码页面而非商品页面")
            
        return self.product_data
    
    def parse_from_file(self, file_path: str, url: str = "") -> ProductData:
        """
        从HTML文件解析商品信息
        
        Args:
            file_path: HTML文件路径
            url: 商品链接(可选)
            
        Returns:
            ProductData 对象
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
            
        # 尝试多种编码读取
        encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030']
        html_content = None
        
        for encoding in encodings:
            try:
                html_content = path.read_text(encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
                
        if html_content is None:
            raise ValueError(f"无法读取文件，请确保文件编码正确: {file_path}")
            
        return self.parse_from_html(html_content, url)
        
    def _extract_title(self, soup: BeautifulSoup):
        """提取商品标题"""
        # 尝试多种选择器 - 1688常用
        selectors = [
            # 新版1688
            'h1.title-text',
            '.title-text',
            '.title-content',
            'h1[class*="title"]',
            '.mod-detail-title h1',
            '[class*="offerTitle"]',
            '.d-title',
            # 旧版1688
            '.d-title',
            '.obj-leading-title',
            '.m-title',
            # 通用
            'h1',
            '.product-title',
            '.item-title',
        ]
        
        for selector in selectors:
            try:
                element = soup.select_one(selector)
                if element and element.get_text(strip=True):
                    title = element.get_text(strip=True)
                    # 清理标题
                    title = re.sub(r'\s+', ' ', title)
                    if len(title) > 5:  # 标题至少5个字符
                        self.product_data.title = title
                        return
            except:
                continue
                
        # 备用方案：从meta标签获取
        meta_selectors = [
            ('meta', {'property': 'og:title'}),
            ('meta', {'name': 'title'}),
            ('meta', {'name': 'keywords'}),
        ]
        
        for tag, attrs in meta_selectors:
            try:
                meta = soup.find(tag, attrs)
                if meta and meta.get('content'):
                    self.product_data.title = meta['content']
                    return
            except:
                continue
                
        # 最后尝试从title标签获取
        try:
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text(strip=True)
                # 移除常见后缀
                title = re.sub(r'[-_|].*?(1688|阿里巴巴|批发).*$', '', title).strip()
                if title:
                    self.product_data.title = title
        except:
            pass
            
    def _extract_price(self, soup: BeautifulSoup):
        """提取价格区间"""
        selectors = [
            '.price-text',
            '[class*="price"]',
            '.mod-detail-price',
            '.d-price',
            '.price-range',
        ]
        
        for selector in selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text(strip=True)
                    # 匹配价格格式: ¥12.00 或 12.00-35.00
                    if re.search(r'[\d.]+', text):
                        # 清理价格文本
                        price = re.sub(r'\s+', '', text)
                        self.product_data.price_range = price
                        return
            except:
                continue
                    
    def _extract_main_images(self, soup: BeautifulSoup, raw_html: str = ""):
        """提取主图列表"""
        images = []
        
        # 方法1: 查找主图容器 (1688常用选择器)
        main_selectors = [
            # 新版1688 主图轮播
            '.detail-gallery-img img',
            '.vertical-img img',
            '.detail-gallery-turn-wrapper img',
            '[class*="mainImg"] img',
            '.mod-detail-gallery img',
            '.gallery-list img',
            '.main-img img',
            '.id-content .gallery img',
            # SKU 规格图
            '.sku-item-image img',
            '.sku-wrapper img',
            '[class*="skuItem"] img',
            '[class*="sku-image"] img',
            '.detail-prop-img img',
            '.obj-sku img',
            # 旧版1688
            '#dt-tab img',
            '.tab-content img',
            '.main-image img',
            '#J_MImage img',
            '.main-img-container img',
            # 通用选择器
            '[class*="thumb"] img',
            '[class*="gallery"] img',
            '[class*="preview"] img',
            '.id-content img',
            '.app-offerdetail_container img',
            # 颜色/规格缩略图
            '[class*="color"] img',
            '[class*="prop"] img',
            # 更宽泛的选择器
            'img[src*="cbu01.alicdn.com"]',
            'img[data-src*="cbu01.alicdn.com"]',
        ]
        
        for selector in main_selectors:
            try:
                elements = soup.select(selector)
                for img in elements:
                    for attr in ['src', 'data-src', 'data-lazy-src', 'data-lazyload-src', 'data-original']:
                        src = img.get(attr)
                        if src:
                            src = self._process_image_url(src)
                            if src and src not in images and self._is_valid_product_image(src):
                                images.append(src)
            except:
                continue
        
        # 方法2: 从script标签中提取JSON数据中的图片
        if raw_html:
            # 匹配 alicdn.com 的图片URL
            patterns = [
                r'"(https?://[^"]*?cbu01\.alicdn\.com[^"]*?\.(?:jpg|jpeg|png|webp)(?:\?[^"]*)?)"',
                r'"(https?://[^"]*?img\.alicdn\.com[^"]*?\.(?:jpg|jpeg|png|webp)(?:\?[^"]*)?)"',
                r"'(https?://[^']*?cbu01\.alicdn\.com[^']*?\.(?:jpg|jpeg|png|webp)(?:\?[^']*)?)'",
            ]
            
            for pattern in patterns:
                try:
                    matches = re.findall(pattern, raw_html, re.I)
                    for url in matches:
                        url = self._process_image_url(url)
                        if url and url not in images and self._is_valid_product_image(url):
                            # 排除详情图
                            if 'descImage' not in url and 'desc-image' not in url:
                                images.append(url)
                except:
                    continue
        
        # 去重并限制数量
        seen = set()
        unique_images = []
        for img in images:
            # 标准化URL再去重
            normalized = re.sub(r'_\d+x\d+\.', '.', img)
            if normalized not in seen:
                seen.add(normalized)
                unique_images.append(img)
                
        self.product_data.main_images = unique_images  # 不限制数量
        
    def _extract_detail_images(self, soup: BeautifulSoup):
        """提取详情页A+图（商品详情描述中的所有图片）"""
        images = []
        
        # A+ 详情区域选择器（覆盖1688各种详情模板）
        detail_selectors = [
            # 新版1688 详情区域
            '.detail-content img',
            '.detail-desc img',
            '.detail-desc-decorate-richtext img',
            '.mod-detail-description img',
            '.offer-detail-content img',
            '.detail-decorate img',
            '#J_DivItemDesc img',
            # A+ 富文本区域
            '[class*="richtext"] img',
            '[class*="RichText"] img',
            '[class*="desc"] img',
            '[class*="Desc"] img',
            '[class*="description"] img',
            '[class*="Description"] img',
            # 懒加载容器
            '#desc-lazyload-container img',
            '.lazyload-wrapper img',
            '[data-spm*="desc"] img',
            # 详情图片容器
            '.offer-attr-item img',
            '.de-description img',
            '.de-box img',
            '.detail-module img',
            '.module-desc img',
            # iframe 内容区域
            '.desc-content img',
            '.offer-desc img',
            # 通用详情图
            '[class*="detail"] img',
            '[class*="Detail"] img',
            '.product-desc img',
        ]
        
        for selector in detail_selectors:
            try:
                elements = soup.select(selector)
                for img in elements:
                    for attr in ['src', 'data-src', 'data-lazy-src', 'data-lazyload-src', 'data-original', 'data-ks-lazyload']:
                        src = img.get(attr)
                        if src:
                            src = self._process_image_url(src)
                            if src and src not in images and src not in self.product_data.main_images:
                                if self._is_valid_product_image(src):
                                    images.append(src)
            except:
                continue
        
        # 查找所有包含"详情"相关的区域
        for div in soup.find_all(['div', 'section', 'article']):
            class_name = ' '.join(div.get('class', []))
            if any(keyword in class_name.lower() for keyword in ['detail', 'desc', 'content', 'rich']):
                for img in div.find_all('img'):
                    for attr in ['src', 'data-src', 'data-lazy-src', 'data-lazyload-src']:
                        src = img.get(attr)
                        if src:
                            src = self._process_image_url(src)
                            if src and src not in images and src not in self.product_data.main_images:
                                if self._is_valid_product_image(src):
                                    images.append(src)
                                    
        self.product_data.detail_images = images
        
    def _extract_specifications(self, soup: BeautifulSoup):
        """提取规格参数"""
        specs = {}
        
        # 查找规格表格
        selectors = [
            '.detail-attributes-item',
            '.mod-detail-attributes tr',
            '[class*="attribute"] li',
            '.obj-attr li',
            '.d-content li',
            '.product-param li',
        ]
        
        for selector in selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text(strip=True)
                    # 尝试拆分键值对
                    if ':' in text or '：' in text:
                        parts = re.split(r'[:：]', text, 1)
                        if len(parts) == 2:
                            key = parts[0].strip()
                            value = parts[1].strip()
                            if key and value and len(key) < 20:
                                specs[key] = value
            except:
                continue
                            
        self.product_data.specifications = specs
        
    def _extract_description(self, soup: BeautifulSoup):
        """提取商品描述"""
        selectors = [
            '.detail-description',
            '.mod-detail-description',
            '[class*="description"] p',
            '.product-desc p',
        ]
        
        descriptions = []
        for selector in selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text(strip=True)
                    if text and len(text) > 10:
                        descriptions.append(text)
            except:
                continue
                    
        self.product_data.description = '\n'.join(descriptions)
        
    def _extract_shop_name(self, soup: BeautifulSoup):
        """提取店铺名称"""
        selectors = [
            '.shop-name',
            '.company-name',
            '[class*="shopName"]',
            '.store-name',
            '.seller-name',
        ]
        
        for selector in selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    self.product_data.shop_name = element.get_text(strip=True)
                    return
            except:
                continue
                
    def _process_image_url(self, url: str) -> Optional[str]:
        """处理图片URL，获取大图"""
        if not url:
            return None
            
        # 确保是HTTPS
        if url.startswith('//'):
            url = 'https:' + url
        elif not url.startswith('http'):
            return None
            
        # 移除缩略图参数，获取原图
        # 常见的1688缩略图参数: _50x50.jpg, _100x100.jpg 等
        url = re.sub(r'_\d+x\d+\.', '.', url)
        
        # 移除URL参数
        url = re.sub(r'\?.*$', '', url)
        
        return url
    
    def _is_valid_product_image(self, url: str) -> bool:
        """检查是否为有效的产品图片URL"""
        if not url:
            return False
            
        # 排除常见的无效图片
        exclude_patterns = [
            'logo', 'icon', 'loading', 'placeholder', 
            'avatar', 'banner', 'ad', 'advertisement',
            'blank', 'empty', '1x1', 'pixel', 'spacer',
            'arrow', 'button', 'sprite', 'common'
        ]
        
        url_lower = url.lower()
        for pattern in exclude_patterns:
            if pattern in url_lower:
                return False
                
        # 检查是否有有效的图片扩展名
        if not re.search(r'\.(jpg|jpeg|png|webp|gif)($|\?)', url_lower):
            return False
            
        # 检查是否为阿里系图片
        valid_domains = ['alicdn.com', 'tbcdn.cn', 'taobaocdn.com']
        if any(domain in url_lower for domain in valid_domains):
            return True
            
        # 其他域名也接受，只要符合图片格式
        return True
    
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


# 便捷函数
def parse_1688_html(html_content: str, url: str = "") -> ProductData:
    """
    解析1688商品HTML
    
    Args:
        html_content: HTML内容
        url: 商品URL(可选)
        
    Returns:
        ProductData 对象
    """
    parser = HTMLParser()
    return parser.parse_from_html(html_content, url)


def parse_1688_file(file_path: str, url: str = "") -> ProductData:
    """
    从文件解析1688商品HTML
    
    Args:
        file_path: HTML文件路径
        url: 商品URL(可选)
        
    Returns:
        ProductData 对象
    """
    parser = HTMLParser()
    return parser.parse_from_file(file_path, url)


if __name__ == "__main__":
    # 测试代码
    print("="*60)
    print("1688 HTML解析器 - 手动模式")
    print("="*60)
    print("\n使用方法:")
    print("1. 打开1688商品页面")
    print("2. 右键 -> 查看页面源代码 (或按 Ctrl+U)")
    print("3. 复制全部HTML内容")
    print("4. 保存为 .html 文件")
    print("5. 运行此脚本并指定文件路径")
    print("\n或者在代码中直接调用:")
    print("  from html_parser import parse_1688_html")
    print("  data = parse_1688_html(html_content)")
    print("  print(data.title)")
    print("  print(data.main_images)")
