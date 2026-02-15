"""
阿里云 OSS 上传工具模块

提供图片上传到阿里云 OSS 并生成公开 URL 的功能。
"""

import os
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict
from utils.logger import log_info, log_error, log_warning


class OSSUploader:
    """阿里云 OSS 上传器"""

    def __init__(self, config):
        """
        初始化 OSS 上传器

        Args:
            config: 配置对象，包含 OSS 相关配置
        """
        self.config = config
        self._bucket = None
        self._auth = None

    def authenticate(self) -> bool:
        """
        连接 OSS 并测试 bucket

        Returns:
            bool: 连接成功返回 True，否则返回 False
        """
        try:
            import oss2
        except ImportError:
            log_error("[OSS] 请先安装 oss2 库: pip install oss2")
            return False

        try:
            # 从配置中读取 OSS 信息
            # 注意：这里需要根据实际的配置结构调整
            access_key_id = getattr(self.config, 'aliyun_oss_access_key_id', None)
            access_key_secret = getattr(self.config, 'aliyun_oss_access_key_secret', None)
            bucket_name = getattr(self.config, 'aliyun_oss_bucket', None)
            endpoint = getattr(self.config, 'aliyun_oss_endpoint', None)

            if not all([access_key_id, access_key_secret, bucket_name, endpoint]):
                log_error("[OSS] OSS 配置不完整")
                return False

            # 贴建认证和 Bucket 对象
            self._auth = oss2.Auth(access_key_id, access_key_secret)
            self._bucket = oss2.Bucket(self._auth, endpoint, bucket_name)

            # 测试连接
            self._bucket.get_bucket_info()
            log_info(f"[OSS] 连接成功: {bucket_name}")
            return True

        except Exception as e:
            log_error(f"[OSS] 连接失败: {e}")
            return False

    def create_folder(self, folder_name: str) -> str:
        """
        贴建文件夹前缀（OSS 无真实文件夹）

        Args:
            folder_name: 文件夹名称

        Returns:
            str: 前缀路径
        """
        # OSS 没有真实的文件夹概念，只是路径前缀
        prefix = getattr(self.config, 'aliyun_oss_prefix', 'images/')
        date_prefix = datetime.now().strftime('%Y/%m/%d')
        return f"{prefix}{date_prefix}/{folder_name}/"

    def upload_file(self, file_path: str, folder_prefix: str) -> Optional[Dict]:
        """
        上传文件到 OSS

        Args:
            file_path: 本地文件路径
            folder_prefix: 文件夹前缀

        Returns:
            dict: 包含 object_key 和 url 的字典，失败返回 None
        """
        if not self._bucket:
            log_error("[OSS] 未连接到 OSS，请先调用 authenticate()")
            return None

        try:
            # 生成唯一的对象名称
            filename = Path(file_path).name
            ext = Path(file_path).suffix or '.jpg'
            unique_name = f"{uuid.uuid4().hex}{ext}"
            object_key = f"{folder_prefix}{unique_name}"

            # 上传文件（带重试）
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    with open(file_path, 'rb') as f:
                        result = self._bucket.put_object(object_key, f)

                    if result.status == 200:
                        url = self.get_direct_link(object_key)
                        log_info(f"[OSS] 上传成功: {filename} -> {url}")
                        return {
                            'object_key': object_key,
                            'url': url,
                            'filename': filename
                        }
                    else:
                        log_warning(f"[OSS] 上传失败 (尝试 {attempt + 1}/{max_retries}): HTTP {result.status}")

                except Exception as e:
                    log_warning(f"[OSS] 上传错误 (尝试 {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(2 * (attempt + 1))  # 递增等待

            log_error(f"[OSS] 上传失败，已重试 {max_retries} 次: {filename}")
            return None

        except Exception as e:
            log_error(f"[OSS] 上传文件失败: {e}")
            return None

    def get_direct_link(self, object_key: str) -> str:
        """
        生成公开访问 URL

        Args:
            object_key: OSS 对象键

        Returns:
            str: 公开访问 URL
        """
        if not self._bucket:
            return ""

        # 格式: https://{bucket}.{endpoint}/{object_key}
        bucket_name = self._bucket.bucket_name
        endpoint = self._bucket.endpoint.replace('https://', '').replace('http://', '')
        return f"https://{bucket_name}.{endpoint}/{object_key}"
