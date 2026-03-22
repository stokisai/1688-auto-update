"""
图片下载器

下载抓取到的图片到本地目录。
"""

import os
import re
import time
import hashlib
import requests
from pathlib import Path
from typing import List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from utils.chrome_version import get_user_agent


class ImageDownloader:
    """图片下载器"""
    
    def __init__(self, output_dir: str = "./output/images", max_workers: int = 5):
        """
        初始化下载器
        
        Args:
            output_dir: 输出目录
            max_workers: 最大并发下载数
        """
        self.output_dir = Path(output_dir)
        self.max_workers = max_workers
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": get_user_agent(),
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
            "Referer": "https://detail.1688.com/",
        })
        
        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def download_images(self, urls: List[str], prefix: str = "img") -> List[Tuple[str, str]]:
        """
        批量下载图片
        
        Args:
            urls: 图片URL列表
            prefix: 文件名前缀
            
        Returns:
            [(url, local_path), ...] 下载成功的图片列表
        """
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for i, url in enumerate(urls):
                filename = f"{prefix}_{i+1:03d}"
                future = executor.submit(self._download_single, url, filename)
                futures[future] = url
                
            for future in as_completed(futures):
                url = futures[future]
                try:
                    local_path = future.result()
                    if local_path:
                        results.append((url, local_path))
                except Exception as e:
                    print(f"下载失败: {url} - {e}")
                    
        return results
    
    def download_main_images(self, urls: List[str]) -> List[Tuple[str, str]]:
        """下载主图"""
        return self.download_images(urls, prefix="main")
    
    def download_detail_images(self, urls: List[str]) -> List[Tuple[str, str]]:
        """下载详情图"""
        return self.download_images(urls, prefix="detail")
    
    def _download_single(self, url: str, filename: str) -> Optional[str]:
        """
        下载单张图片
        
        Args:
            url: 图片URL
            filename: 文件名(不含扩展名)
            
        Returns:
            本地保存路径，失败返回None
        """
        try:
            # 获取扩展名
            ext = self._get_extension(url)
            
            # 构建完整路径
            local_path = self.output_dir / f"{filename}{ext}"
            
            # 如果文件已存在，跳过
            if local_path.exists():
                return str(local_path)
                
            # 下载
            response = self.session.get(url, timeout=30, stream=True)
            response.raise_for_status()
            
            # 检查内容类型
            content_type = response.headers.get('Content-Type', '')
            if not content_type.startswith('image/'):
                # 尝试检测文件头
                content = response.content
                if not self._is_valid_image(content):
                    return None
            else:
                content = response.content
            
            # 检查文件大小 - 小于5KB很可能是图标
            if len(content) < 5000:
                return None
            
            # 检查文件大小 - 大于10MB可能有问题
            if len(content) > 10 * 1024 * 1024:
                return None
                
            # 保存文件
            with open(local_path, 'wb') as f:
                f.write(content)
            
            # 检查图片尺寸
            if not self._check_image_dimensions(local_path):
                # 删除小图标
                try:
                    local_path.unlink()
                except:
                    pass
                return None
                
            return str(local_path)
            
        except requests.exceptions.RequestException as e:
            return None
        except Exception as e:
            return None
    
    def _check_image_dimensions(self, image_path: Path) -> bool:
        """检查图片尺寸，过滤掉小图标"""
        try:
            from PIL import Image
            with Image.open(image_path) as img:
                width, height = img.size
                
                # 尺寸太小，很可能是图标
                if width < 150 or height < 150:
                    return False
                
                # 正方形小图通常是图标
                if width == height and width < 200:
                    return False
                    
                return True
        except ImportError:
            # 如果没有PIL，跳过尺寸检查
            return True
        except Exception:
            # 无法读取图片，可能已损坏
            return False
    
    def _get_extension(self, url: str) -> str:
        """获取图片扩展名"""
        # 从URL路径获取
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']:
            if ext in path:
                return ext
                
        # 默认使用jpg
        return '.jpg'
    
    def _is_valid_image(self, content: bytes) -> bool:
        """检查是否为有效图片"""
        if len(content) < 8:
            return False
            
        # 检查常见图片文件头
        headers = {
            b'\xff\xd8\xff': 'jpg',
            b'\x89PNG\r\n\x1a\n': 'png',
            b'GIF87a': 'gif',
            b'GIF89a': 'gif',
            b'RIFF': 'webp',  # WebP (简化检查)
        }
        
        for header, fmt in headers.items():
            if content.startswith(header):
                return True
                
        return False
    
    def clear_output_dir(self):
        """清空输出目录"""
        import shutil
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def get_downloaded_files(self) -> List[str]:
        """获取已下载的文件列表"""
        if not self.output_dir.exists():
            return []
        return [str(f) for f in self.output_dir.iterdir() if f.is_file()]
