"""
图片上传图床工具模块

支持将本地图片上传到图床服务并获取URL。
支持的服务：
- ImgBB (免费推荐)
- Imgur
- Cloudinary
- 自定义图床
"""

import os
import base64
import requests
from pathlib import Path
from typing import Optional, Dict, Any
from PIL import Image
import io


class ImageHostClient:
    """图床客户端基类"""

    def upload(self, image_path: str) -> str:
        """上传图片并返回URL"""
        raise NotImplementedError


class ImgBBClient(ImageHostClient):
    """ImgBB 图床客户端

    免费图床服务，访问 https://api.imgbb.com/ 获取 API Key
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://api.imgbb.com/1/upload"

    def upload(self, image_path: str) -> str:
        """上传图片到 ImgBB

        Args:
            image_path: 图片文件路径

        Returns:
            图片URL

        Raises:
            ValueError: 上传失败
        """
        if not self.api_key:
            raise ValueError("ImgBB API Key 未配置")

        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")

        try:
            # 读取图片
            with open(image_path, 'rb') as f:
                image_data = f.read()

            # 准备上传数据
            files = {'image': (os.path.basename(image_path), image_data, 'image/jpeg')}
            data = {'key': self.api_key}

            response = requests.post(
                self.api_url,
                files=files,
                data=data,
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    return result['data']['url']
                else:
                    error_msg = result.get('error', {}).get('message', '未知错误')
                    raise ValueError(f"ImgBB 上传失败: {error_msg}")
            else:
                raise ValueError(f"ImgBB API 错误: HTTP {response.status_code}")

        except requests.exceptions.RequestException as e:
            raise ValueError(f"ImgBB 网络请求失败: {e}")


class ImgurClient(ImageHostClient):
    """Imgur 图床客户端

    访问 https://api.imgur.com/ 获取 Client ID
    """

    def __init__(self, client_id: str):
        self.client_id = client_id
        self.api_url = "https://api.imgur.com/3/image"

    def upload(self, image_path: str) -> str:
        """上传图片到 Imgur

        Args:
            image_path: 图片文件路径

        Returns:
            图片URL

        Raises:
            ValueError: 上传失败
        """
        if not self.client_id:
            raise ValueError("Imgur Client ID 未配置")

        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")

        try:
            # 读取并编码图片
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')

            # 准备请求
            headers = {
                'Authorization': f'Client-ID {self.client_id}'
            }
            data = {
                'image': image_data,
                'type': 'base64',
            }

            response = requests.post(
                self.api_url,
                headers=headers,
                data=data,
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    return result['data']['link']
                else:
                    error_msg = result.get('data', {}).get('error', '未知错误')
                    raise ValueError(f"Imgur 上传失败: {error_msg}")
            else:
                raise ValueError(f"Imgur API 错误: HTTP {response.status_code}")

        except requests.exceptions.RequestException as e:
            raise ValueError(f"Imgur 网络请求失败: {e}")


class CloudinaryClient(ImageHostClient):
    """Cloudinary 图床客户端

    需要配置 cloud_name、api_key 和 api_secret
    """

    def __init__(self, cloud_name: str, api_key: str, api_secret: str):
        self.cloud_name = cloud_name
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_url = f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"

    def upload(self, image_path: str) -> str:
        """上传图片到 Cloudinary

        Args:
            image_path: 图片文件路径

        Returns:
            图片URL

        Raises:
            ValueError: 上传失败
        """
        if not all([self.cloud_name, self.api_key, self.api_secret]):
            raise ValueError("Cloudinary 配置不完整")

        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")

        try:
            # 读取图片
            with open(image_path, 'rb') as f:
                files = {'file': (os.path.basename(image_path), f, 'image/jpeg')}

            # 准备认证
            auth = (self.api_key, self.api_secret)

            # 公开上传参数
            data = {
                'upload_preset': 'unsigned_preset',  # 需要在 Cloudinary 后台配置
            }

            response = requests.post(
                self.api_url,
                files=files,
                data=data,
                auth=auth,
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                if 'url' in result:
                    return result['url']
                elif 'secure_url' in result:
                    return result['secure_url']
                else:
                    raise ValueError(f"Cloudinary 上传失败: 未返回URL")
            else:
                error_msg = response.json().get('error', {}).get('message', '未知错误')
                raise ValueError(f"Cloudinary API 错误: {error_msg}")

        except requests.exceptions.RequestException as e:
            raise ValueError(f"Cloudinary 网络请求失败: {e}")


class CustomImageHostClient(ImageHostClient):
    """自定义图床客户端

    支持自定义的上传API和认证方式
    """

    def __init__(self, upload_url: str, auth_header: str = "", response_path: str = "url"):
        """
        Args:
            upload_url: 上传API地址
            auth_header: 认证头 (例如: "Bearer xxx")
            response_path: 响应中URL的JSON路径 (例如: "data.url")
        """
        self.upload_url = upload_url
        self.auth_header = auth_header
        self.response_path = response_path

    def upload(self, image_path: str) -> str:
        """上传图片到自定义图床

        Args:
            image_path: 图片文件路径

        Returns:
            图片URL

        Raises:
            ValueError: 上传失败
        """
        if not self.upload_url:
            raise ValueError("自定义图床 URL 未配置")

        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")

        try:
            # 准备请求
            headers = {}
            if self.auth_header:
                headers['Authorization'] = self.auth_header

            with open(image_path, 'rb') as f:
                files = {'file': (os.path.basename(image_path), f, 'image/jpeg')}

            response = requests.post(
                self.upload_url,
                files=files,
                headers=headers,
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()

                # 从响应中提取URL
                url = self._extract_from_json(result, self.response_path)
                if url:
                    return url
                else:
                    raise ValueError(f"自定义图床响应中未找到URL (路径: {self.response_path})")
            else:
                raise ValueError(f"自定义图床 API 错误: HTTP {response.status_code}")

        except requests.exceptions.RequestException as e:
            raise ValueError(f"自定义图床网络请求失败: {e}")

    def _extract_from_json(self, data: Dict, path: str) -> Optional[str]:
        """从JSON中按路径提取值"""
        keys = path.split('.')
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current if isinstance(current, str) else None


class AliyunOSSClient(ImageHostClient):
    """阿里云 OSS 图床客户端

    需要配置 access_key_id、access_key_secret、bucket 和 endpoint
    访问 https://oss.console.aliyun.com/ 获取配置信息
    """

    def __init__(self, access_key_id: str, access_key_secret: str, bucket: str, endpoint: str):
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.bucket = bucket
        self.endpoint = endpoint

    def upload(self, image_path: str) -> str:
        """上传图片到阿里云 OSS

        Args:
            image_path: 图片文件路径

        Returns:
            图片URL

        Raises:
            ValueError: 上传失败
        """
        if not all([self.access_key_id, self.access_key_secret, self.bucket, self.endpoint]):
            raise ValueError("阿里云 OSS 配置不完整")

        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")

        try:
            import oss2
        except ImportError:
            raise ValueError("请先安装 oss2 库: pip install oss2")

        try:
            # 贴建 OSS 认证和 Bucket 对象
            auth = oss2.Auth(self.access_key_id, self.access_key_secret)
            bucket = oss2.Bucket(auth, self.endpoint, self.bucket)

            # 生成唯一的对象名称
            import uuid
            from datetime import datetime
            ext = os.path.splitext(image_path)[1] or '.jpg'
            date_prefix = datetime.now().strftime('%Y/%m/%d')
            object_key = f"images/{date_prefix}/{uuid.uuid4().hex}{ext}"

            # 上传文件
            with open(image_path, 'rb') as f:
                result = bucket.put_object(object_key, f)

            if result.status == 200:
                # 生成公开访问 URL
                # 格式: https://{bucket}.{endpoint}/{object_key}
                # 移除 endpoint 中的 https:// 前缀（如果存在）
                endpoint_clean = self.endpoint.replace('https://', '').replace('http://', '')
                url = f"https://{self.bucket}.{endpoint_clean}/{object_key}"
                return url
            else:
                raise ValueError(f"阿里云 OSS 上传失败: HTTP {result.status}")

        except Exception as e:
            if 'oss2' in str(type(e).__module__):
                raise ValueError(f"阿里云 OSS 错误: {e}")
            raise ValueError(f"阿里云 OSS 上传失败: {e}")


class ImageHostUploader:
    """图片上传器 - 自动选择可用的图床服务"""

    def __init__(self, config):
        """
        Args:
            config: ImageURLConfig 配置对象
        """
        self.config = config
        self._clients = {}

    def _get_available_client(self) -> ImageHostClient:
        """获取第一个可用的图床客户端"""
        # 检查 Imgur
        if self.config.imgur_client_id:
            if 'imgur' not in self._clients:
                self._clients['imgur'] = ImgurClient(self.config.imgur_client_id)
            return self._clients['imgur']

        # 检查 ImgBB
        if self.config.imgbb_api_key:
            if 'imgbb' not in self._clients:
                self._clients['imgbb'] = ImgBBClient(self.config.imgbb_api_key)
            return self._clients['imgbb']

        # 检查 Cloudinary
        if self.config.cloudinary_cloud_name and self.config.cloudinary_api_key:
            if 'cloudinary' not in self._clients:
                self._clients['cloudinary'] = CloudinaryClient(
                    self.config.cloudinary_cloud_name,
                    self.config.cloudinary_api_key,
                    self.config.cloudinary_api_secret
                )
            return self._clients['cloudinary']

        # 检查自定义图床
        if self.config.custom_upload_url:
            if 'custom' not in self._clients:
                self._clients['custom'] = CustomImageHostClient(
                    self.config.custom_upload_url,
                    self.config.custom_auth_header
                )
            return self._clients['custom']

        # 检查阿里云 OSS
        if self.config.aliyun_oss_access_key_id and self.config.aliyun_oss_bucket:
            if 'aliyun_oss' not in self._clients:
                self._clients['aliyun_oss'] = AliyunOSSClient(
                    self.config.aliyun_oss_access_key_id,
                    self.config.aliyun_oss_access_key_secret,
                    self.config.aliyun_oss_bucket,
                    self.config.aliyun_oss_endpoint
                )
            return self._clients['aliyun_oss']

        raise ValueError("没有可用的图床服务配置")

    def upload(self, image_path: str, service: Optional[str] = None) -> str:
        """
        上传图片到图床

        Args:
            image_path: 图片文件路径
            service: 指定使用的服务 ("imgbb", "imgur", "cloudinary", "custom")，
                     如果为 None 则自动选择第一个可用服务

        Returns:
            图片URL

        Raises:
            ValueError: 上传失败或没有可用的图床服务
        """
        if service:
            # 使用指定服务
            if service == "imgbb":
                if not self.config.imgbb_api_key:
                    raise ValueError("ImgBB 未配置")
                client = ImgBBClient(self.config.imgbb_api_key)
            elif service == "imgur":
                if not self.config.imgur_client_id:
                    raise ValueError("Imgur 未配置")
                client = ImgurClient(self.config.imgur_client_id)
            elif service == "cloudinary":
                if not all([self.config.cloudinary_cloud_name, self.config.cloudinary_api_key]):
                    raise ValueError("Cloudinary 未配置")
                client = CloudinaryClient(
                    self.config.cloudinary_cloud_name,
                    self.config.cloudinary_api_key,
                    self.config.cloudinary_api_secret
                )
            elif service == "custom":
                if not self.config.custom_upload_url:
                    raise ValueError("自定义图床未配置")
                client = CustomImageHostClient(
                    self.config.custom_upload_url,
                    self.config.custom_auth_header
                )
            elif service == "aliyun_oss":
                if not all([self.config.aliyun_oss_access_key_id, self.config.aliyun_oss_bucket]):
                    raise ValueError("阿里云 OSS 未配置")
                client = AliyunOSSClient(
                    self.config.aliyun_oss_access_key_id,
                    self.config.aliyun_oss_access_key_secret,
                    self.config.aliyun_oss_bucket,
                    self.config.aliyun_oss_endpoint
                )
            else:
                raise ValueError(f"不支持的图床服务: {service}")
        else:
            # 自动选择可用服务
            client = self._get_available_client()

        return client.upload(image_path)

    def is_available(self) -> bool:
        """检查是否有可用的图床服务"""
        return self.config.is_configured()


def image_to_url(image_path: str, config) -> str:
    """
    便捷函数：将本地图片转换为URL

    Args:
        image_path: 图片文件路径
        config: ImageURLConfig 配置对象

    Returns:
        图片URL

    Raises:
        ValueError: 转换失败
    """
    uploader = ImageHostUploader(config)
    return uploader.upload(image_path)
