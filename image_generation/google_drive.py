"""
Google Drive 上传模块

支持将文件上传到 Google Drive 云存储。
需要 OAuth 2.0 认证。

使用说明：
1. 访问 Google Cloud Console (https://console.cloud.google.com/)
2. 贴建项目或选择现有项目
3. 启用 Google Drive API
4. 贴建 OAuth 2.0 客户端 ID (应用程序类型: 桌面应用)
5. 获取客户端 ID 和客户端密钥
"""

import os
import json
import time
import webbrowser
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime, timedelta
import urllib.parse
import urllib.request
import urllib.error

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class GoogleDriveAuth:
    """Google Drive OAuth 2.0 认证管理器"""

    # OAuth 2.0 端点
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"

    # OAuth 2.0 作用域
    SCOPES = [
        "https://www.googleapis.com/auth/drive.file",  # 访问用户贴建或打开的文件
    ]

    # 重定向 URI (本地)
    REDIRECT_URI = "http://localhost:8080"

    def __init__(self, client_id: str, client_secret: str):
        """
        Args:
            client_id: OAuth 2.0 客户端 ID
            client_secret: OAuth 2.0 客户端密钥
        """
        self.client_id = client_id
        self.client_secret = client_secret

    def get_auth_url(self) -> str:
        """生成授权 URL"""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.REDIRECT_URI,
            "scope": " ".join(self.SCOPES),
            "response_type": "code",
            "access_type": "offline",  # 获取刷新令牌
            "prompt": "consent",  # 强制显示同意屏幕以获取刷新令牌
        }

        return f"{self.AUTH_URL}?{urllib.parse.urlencode(params)}"

    def exchange_code_for_token(self, auth_code: str) -> Dict:
        """
        用授权码交换访问令牌

        Args:
            auth_code: 从授权回调中获取的授权码

        Returns:
            包含访问令牌、刷新令牌等信息的字典
        """
        data = {
            "code": auth_code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.REDIRECT_URI,
            "grant_type": "authorization_code",
        }

        req = urllib.request.Request(
            self.TOKEN_URL,
            data=urllib.parse.urlencode(data).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            raise ValueError(f"令牌交换失败: {error_body}")
        except Exception as e:
            raise ValueError(f"令牌交换失败: {e}")

    def refresh_access_token(self, refresh_token: str) -> Dict:
        """
        刷新访问令牌

        Args:
            refresh_token: 刷新令牌

        Returns:
            包含新访问令牌的字典
        """
        data = {
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
        }

        req = urllib.request.Request(
            self.TOKEN_URL,
            data=urllib.parse.urlencode(data).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as e:
            raise ValueError(f"令牌刷新失败: {e}")

    def authenticate_with_browser(self, port: int = 8080) -> Dict:
        """
        通过浏览器进行完整的 OAuth 认证流程

        Args:
            port: 本地服务器端口

        Returns:
            包含令牌信息的字典
        """
        auth_url = self.get_auth_url()

        print(f"正在打开浏览器进行授权...")
        print(f"如果没有自动打开，请访问: {auth_url}")

        # 打开浏览器
        webbrowser.open(auth_url)

        # 贴建简单的本地 HTTP 服务器来接收回调
        import http.server
        import socketserver

        auth_result = {"code": None, "error": None}

        class CallbackHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                # 解析查询参数
                parsed = urllib.parse.urlparse(self.path)
                params = urllib.parse.parse_qs(parsed.query)

                if "code" in params:
                    auth_result["code"] = params["code"][0]
                    self.send_response(200)
                    self.send_header("Content-type", "text/html; charset=utf-8")
                    self.end_headers()
                    response_html = """
                        <html><head><title>Authentication Successful</title></head>
                        <body>
                            <h1>Authentication Successful!</h1>
                            <p>You can close this window and return to the application.</p>
                        </body>
                        </html>
                    """.encode("utf-8")
                    self.wfile.write(response_html)
                elif "error" in params:
                    auth_result["error"] = params["error"][0]
                    self.send_response(400)
                    self.send_header("Content-type", "text/html; charset=utf-8")
                    self.end_headers()
                    error_msg = params["error"][0]
                    response_html = f"""
                        <html><head><title>Authentication Failed</title></head>
                        <body>
                            <h1>Authentication Failed</h1>
                            <p>Error: {error_msg}</p>
                        </body>
                        </html>
                    """.encode("utf-8")
                    self.wfile.write(response_html)
                else:
                    self.send_response(400)
                    self.end_headers()

            def log_message(self, format, *args):
                pass  # 禁用日志输出

        # 启动服务器
        with socketserver.TCPServer(("localhost", port), CallbackHandler) as httpd:
            httpd.timeout = 120  # 2 分钟超时

            # 等待回调
            start_time = time.time()
            while auth_result["code"] is None and auth_result["error"] is None:
                if time.time() - start_time > 120:
                    raise ValueError("认证超时，请重试")
                httpd.handle_request()

        if auth_result["error"]:
            raise ValueError(f"认证失败: {auth_result['error']}")

        # 交换授权码获取令牌
        return self.exchange_code_for_token(auth_result["code"])


class GoogleDriveClient:
    """Google Drive 客户端"""

    API_BASE = "https://www.googleapis.com/drive/v3/files"
    UPLOAD_BASE = "https://www.googleapis.com/upload/drive/v3/files"

    def __init__(self, config, config_save_callback=None):
        """
        Args:
            config: GoogleDriveConfig 配置对象
            config_save_callback: 配置保存回调函数（用于保存刷新的令牌）
        """
        self.config = config
        self.config_save_callback = config_save_callback
        self.auth = GoogleDriveAuth(config.client_id, config.client_secret)

    def _ensure_valid_token(self):
        """确保有有效的访问令牌"""
        if self.config.needs_refresh():
            self._refresh_token()

    def _refresh_token(self):
        """刷新访问令牌"""
        if not self.config.refresh_token:
            raise ValueError("未认证，请先进行 OAuth 认证")

        token_info = self.auth.refresh_access_token(self.config.refresh_token)

        # 更新配置
        self.config.access_token = token_info.get("access_token", "")
        expires_in = token_info.get("expires_in", 3600)
        expiry_time = datetime.now() + timedelta(seconds=expires_in)
        self.config.token_expiry = expiry_time.isoformat()

        # 保存配置
        if self.config_save_callback:
            self.config_save_callback()

    def authenticate(self) -> Dict:
        """
        执行完整的 OAuth 认证流程

        Returns:
            认证结果字典
        """
        if not self.config.is_configured():
            raise ValueError("请先配置 Client ID 和 Client Secret")

        try:
            # 通过浏览器进行认证
            token_info = self.auth.authenticate_with_browser()

            # 保存令牌信息到配置
            self.config.access_token = token_info.get("access_token", "")
            self.config.refresh_token = token_info.get("refresh_token", "")

            expires_in = token_info.get("expires_in", 3600)
            expiry_time = datetime.now() + timedelta(seconds=expires_in)
            self.config.token_expiry = expiry_time.isoformat()

            # 保存配置
            if self.config_save_callback:
                self.config_save_callback()

            return {
                "success": True,
                "message": "认证成功！",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def _get_headers(self) -> Dict:
        """获取 API 请求头"""
        self._ensure_valid_token()
        return {
            "Authorization": f"Bearer {self.config.access_token}",
        }

    def find_or_create_folder(self, folder_name: str) -> str:
        """
        查找或贴建文件夹

        Args:
            folder_name: 文件夹名称

        Returns:
            文件夹 ID
        """
        headers = self._get_headers()

        # 先搜索现有文件夹
        search_query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        search_url = f"{self.API_BASE}?q={urllib.parse.quote(search_query)}&fields=files(id,name)"

        req = urllib.request.Request(search_url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
                if result.get("files"):
                    # 找到现有文件夹
                    return result["files"][0]["id"]
        except Exception as e:
            print(f"搜索文件夹失败: {e}")

        # 贴建新文件夹
        folder_metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        }

        req = urllib.request.Request(
            self.API_BASE,
            data=json.dumps(folder_metadata).encode("utf-8"),
            headers={
                **headers,
                "Content-Type": "application/json",
            }
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result["id"]

    def upload_file(
        self,
        file_path: str,
        folder_id: Optional[str] = None,
        file_name: Optional[str] = None,
    ) -> Dict:
        """
        上传文件到 Google Drive

        Args:
            file_path: 本地文件路径
            folder_id: 目标文件夹 ID（如果为 None，则使用配置中的文件夹或自动贴建）
            file_name: 上传后的文件名（如果为 None，则使用原文件名）

        Returns:
            包含文件信息的字典
        """
        if not self.config.is_authenticated():
            raise ValueError("未认证，请先进行 OAuth 认证")

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        # 确定目标文件夹
        if not folder_id:
            if self.config.folder_id:
                folder_id = self.config.folder_id
            else:
                # 自动贴建文件夹
                folder_id = self.find_or_create_folder(self.config.folder_name)

        # 确定文件名
        if not file_name:
            file_name = os.path.basename(file_path)

        # 读取文件内容
        with open(file_path, "rb") as f:
            file_content = f.read()

        # 准备元数据
        metadata = {
            "name": file_name,
            "parents": [folder_id] if folder_id else [],
        }

        # 分块上传（小文件）或可恢复上传（大文件）
        file_size = len(file_content)

        if file_size < 5 * 1024 * 1024:  # 小于 5MB，使用简单上传
            return self._simple_upload(metadata, file_content)
        else:
            return self._resumable_upload(metadata, file_content, file_size)

    def _simple_upload(self, metadata: Dict, file_content: bytes) -> Dict:
        """简单上传（适用于小文件）"""
        headers = self._get_headers()

        # 构建 multipart 请求
        boundary = "-------314159265358979323846"
        headers["Content-Type"] = f"multipart/related; boundary={boundary}"

        body = b""

        # 添加元数据部分
        body += f"--{boundary}\r\n".encode()
        body += b"Content-Type: application/json; charset=UTF-8\r\n\r\n"
        body += json.dumps(metadata).encode("utf-8")
        body += b"\r\n\r\n"

        # 添加文件内容部分
        body += f"--{boundary}\r\n".encode()
        body += b"Content-Type: image/jpeg\r\n\r\n"
        body += file_content
        body += f"\r\n--{boundary}--\r\n".encode()

        # 发送请求
        upload_url = f"{self.UPLOAD_BASE}?uploadType=multipart&fields=id,name,webViewLink,webContentLink"

        req = urllib.request.Request(upload_url, data=body, headers=headers)

        with urllib.request.urlopen(req, timeout=300) as response:
            return json.loads(response.read().decode("utf-8"))

    def _resumable_upload(self, metadata: Dict, file_content: bytes, file_size: int) -> Dict:
        """可恢复上传（适用于大文件）"""
        headers = self._get_headers()

        # 初始化上传
        init_headers = {
            **headers,
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "image/jpeg",
            "X-Upload-Content-Length": str(file_size),
        }

        init_url = f"{self.UPLOAD_BASE}?uploadType=resumable&fields=id,name,webViewLink,webContentLink"

        req = urllib.request.Request(
            init_url,
            data=json.dumps(metadata).encode("utf-8"),
            headers=init_headers
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            upload_url = response.headers.get("Location")

        # 上传文件内容
        upload_headers = {
            **headers,
            "Content-Type": "image/jpeg",
            "Content-Length": str(file_size),
        }

        req = urllib.request.Request(upload_url, data=file_content, headers=upload_headers)

        with urllib.request.urlopen(req, timeout=300) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_connection(self) -> bool:
        """测试连接是否正常"""
        try:
            self._ensure_valid_token()
            headers = self._get_headers()

            # 获取关于驱动器的信息
            req = urllib.request.Request(
                "https://www.googleapis.com/drive/v3/about?fields=user",
                headers=headers
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                return True
        except Exception:
            return False


class GoogleDriveUploader:
    """Google Drive 上传器 - 便捷封装"""

    def __init__(self, config, config_save_callback=None):
        """
        Args:
            config: GoogleDriveConfig 配置对象
            config_save_callback: 配置保存回调函数
        """
        self.config = config
        self.client = GoogleDriveClient(config, config_save_callback)

    def upload(
        self,
        file_path: str,
        folder_id: Optional[str] = None,
        file_name: Optional[str] = None,
    ) -> Dict:
        """
        上传文件到 Google Drive

        Args:
            file_path: 本地文件路径
            folder_id: 目标文件夹 ID
            file_name: 上传后的文件名

        Returns:
            包含文件信息和链接的字典
        """
        try:
            result = self.client.upload_file(file_path, folder_id, file_name)

            return {
                "success": True,
                "file_id": result.get("id"),
                "file_name": result.get("name"),
                "view_link": result.get("webViewLink"),
                "download_link": result.get("webContentLink"),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def authenticate(self) -> Dict:
        """执行 OAuth 认证"""
        return self.client.authenticate()

    def is_authenticated(self) -> bool:
        """检查是否已认证"""
        return self.config.is_authenticated()

    def test_connection(self) -> bool:
        """测试连接"""
        return self.client.test_connection()


def upload_to_google_drive(
    file_path: str,
    config,
    folder_id: Optional[str] = None,
    file_name: Optional[str] = None,
) -> Dict:
    """
    便捷函数：上传文件到 Google Drive

    Args:
        file_path: 本地文件路径
        config: GoogleDriveConfig 配置对象
        folder_id: 目标文件夹 ID
        file_name: 上传后的文件名

    Returns:
        包含文件信息和链接的字典
    """
    uploader = GoogleDriveUploader(config)
    return uploader.upload(file_path, folder_id, file_name)
