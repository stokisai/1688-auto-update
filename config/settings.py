"""
配置管理模块

支持多用户配置，每个用户的API Key保存在本地。
"""

import json
import os
import sys
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Any


# 配置文件路径（固定到程序根目录，避免误读 _internal/user_config.json）
def _get_app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]

BASE_DIR = _get_app_base_dir()
CONFIG_FILE = BASE_DIR / "user_config.json"
WORKFLOWS_DIR = BASE_DIR / "config" / "workflows"


@dataclass
class APIKeyConfig:
    """API Key 配置，每种类型至少需要一个"""
    
    # 图像识别 API (至少配置一个)
    doubao_api_key: str = ""          # 豆包 (推荐)
    qwen_api_key: str = ""            # 通义千问
    gemini_api_key: str = ""          # Google Gemini
    openrouter_api_key: str = ""      # OpenRouter (通用)
    openai_api_key: str = ""          # OpenAI GPT-4V
    google_cloud_credentials: str = "" # Google Cloud Vision 凭证文件路径
    kling_api_key: str = ""           # 快手可灵
    
    # 图生图 API (至少配置一个)
    nano_banana_api_key: str = ""     # Nano Banana (基于Google Gemini)
    nano_banana_pro_api_key: str = "" # Nano Banana Pro
    # OpenRouter 可复用上面的 key
    # ComfyUI 不需要 API Key，只需服务器地址
    
    def has_recognition_api(self) -> bool:
        """检查是否配置了至少一个图像识别API"""
        return any([
            self.doubao_api_key,
            self.qwen_api_key,
            self.gemini_api_key,
            self.openrouter_api_key,
            self.openai_api_key,
            self.google_cloud_credentials,
            self.kling_api_key,
        ])
    
    def has_generation_api(self) -> bool:
        """检查是否配置了至少一个图生图API"""
        return any([
            self.nano_banana_api_key,
            self.nano_banana_pro_api_key,
            self.gemini_api_key,
            self.openrouter_api_key,  # OpenRouter 也支持图生图
        ])
    
    def get_available_recognition_engines(self) -> List[str]:
        """获取可用的图像识别引擎列表"""
        engines = []
        if self.doubao_api_key: 
            engines.append("doubao")
        if self.qwen_api_key: 
            engines.append("qwen")
        if self.gemini_api_key: 
            engines.append("gemini")
        if self.openrouter_api_key: 
            engines.append("openrouter")
        if self.openai_api_key: 
            engines.append("openai")
        if self.google_cloud_credentials: 
            engines.append("google_vision")
        if self.kling_api_key: 
            engines.append("kling")
        return engines
    
    def get_available_generation_engines(self) -> List[str]:
        """获取可用的图生图引擎列表"""
        engines = []
        has_gemini = bool(self.gemini_api_key)
        if self.nano_banana_api_key or has_gemini:
            engines.append("nano_banana")
        if self.nano_banana_pro_api_key or has_gemini:
            engines.append("nano_banana_pro")
        if self.openrouter_api_key:
            engines.append("openrouter")
        return engines


@dataclass
class WorkflowConfig:
    """单个工作流配置"""
    name: str
    json_content: dict
    prompt_node_id: str           # 例如 "6"
    prompt_param_path: str        # 例如 "inputs.text"
    description: str = ""


@dataclass
class ImageURLConfig:
    """图片链接/图床配置 - 将本地图片转换为URL"""

    # 图床服务类型
    service_type: str = ""  # 可选: "imgbb", "imgur", "cloudinary", "custom"

    # ImgBB 配置 (免费推荐)
    imgbb_api_key: str = ""

    # Imgur 配置
    imgur_client_id: str = ""

    # Cloudinary 配置
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    # 自定义图床
    custom_upload_url: str = ""  # 自定义上传API地址
    custom_auth_header: str = ""  # 自定义认证头 (例如: "Bearer xxx")

    # 阿里云 OSS 配置
    aliyun_oss_access_key_id: str = ""
    aliyun_oss_access_key_secret: str = ""
    aliyun_oss_bucket: str = ""
    aliyun_oss_endpoint: str = ""  # 例如: oss-cn-hangzhou.aliyuncs.com

    def get_available_services(self) -> List[str]:
        """获取已配置的图床服务列表"""
        services = []
        if self.imgur_client_id:
            services.append("imgur")
        if self.imgbb_api_key:
            services.append("imgbb")
        if self.cloudinary_cloud_name and self.cloudinary_api_key and self.cloudinary_api_secret:
            services.append("cloudinary")
        if self.custom_upload_url:
            services.append("custom")
        if self.aliyun_oss_access_key_id and self.aliyun_oss_access_key_secret and self.aliyun_oss_bucket and self.aliyun_oss_endpoint:
            services.append("aliyun_oss")
        return services

    def is_configured(self) -> bool:
        """检查是否配置了至少一个图床服务"""
        return len(self.get_available_services()) > 0


@dataclass
class GoogleDriveConfig:
    """Google Drive 云存储配置"""

    # OAuth 2.0 凭证 (从 Google Cloud Console 获取)
    client_id: str = ""          # OAuth 2.0 客户端 ID
    client_secret: str = ""      # OAuth 2.0 客户端密钥
    refresh_token: str = ""      # 刷新令牌 (认证后自动获取)

    # 上传配置
    folder_id: str = ""          # 目标文件夹 ID (可选，留空则上传到根目录)
    folder_name: str = "1688自动化工具"  # 自动创建的文件夹名称

    # 认证状态
    access_token: str = ""       # 当前访问令牌
    token_expiry: str = ""       # 令牌过期时间 (ISO 格式)

    def is_configured(self) -> bool:
        """检查是否已完成基本配置"""
        return bool(self.client_id and self.client_secret)

    def is_authenticated(self) -> bool:
        """检查是否已完成认证"""
        return bool(self.refresh_token)

    def needs_refresh(self) -> bool:
        """检查是否需要刷新访问令牌"""
        if not self.access_token or not self.token_expiry:
            return True

        try:
            from datetime import datetime
            expiry = datetime.fromisoformat(self.token_expiry)
            # 如果令牌将在 5 分钟内过期，则需要刷新
            return datetime.now() >= expiry - datetime.timedelta(minutes=5)
        except:
            return True


@dataclass
class ComfyUIConfig:
    """ComfyUI 配置"""
    server_url: str = ""              # GPU服务器地址 (每次需确认)
    auth_username: str = ""           # 认证服务器账号
    auth_password: str = ""           # 认证服务器密码
    auth_server_url: str = ""         # 认证服务器地址 (如 wp08.unicron.org.cn:端口)
    current_workflow: str = ""         # 当前使用的工作流名称
    workflows: Dict[str, dict] = field(default_factory=dict)  # 工作流列表
    last_used: str = ""               # 上次使用时间

    def get_effective_server_url(self) -> str:
        """获取有效的服务器地址（优先使用直连地址，否则用认证地址）"""
        if self.server_url and self.server_url.strip():
            return self.server_url.strip()
        if self.auth_username and self.auth_password and self.auth_server_url:
            host = self.auth_server_url.strip()
            # 去掉用户可能输入的协议前缀
            for prefix in ("https://", "http://"):
                if host.lower().startswith(prefix):
                    host = host[len(prefix):]
                    break
            from urllib.parse import quote
            user = quote(self.auth_username.strip(), safe="")
            pwd = quote(self.auth_password.strip(), safe="")
            return f"https://{user}:{pwd}@{host}"
        return ""
    
    def add_workflow(self, name: str, json_content: dict,
                     prompt_node_id: str, prompt_param_path: str,
                     description: str = "",
                     image_node_id: str = None, image_param_path: str = None):
        """添加新工作流"""
        self.workflows[name] = {
            "json": json_content,
            "prompt_node_id": prompt_node_id,
            "prompt_param_path": prompt_param_path,
            "description": description,
        }
        # 如果检测到图片节点，也保存
        if image_node_id:
            self.workflows[name]["image_node_id"] = image_node_id
            self.workflows[name]["image_param_path"] = image_param_path
        if not self.current_workflow:
            self.current_workflow = name
        
    def remove_workflow(self, name: str) -> bool:
        """删除工作流"""
        if name in self.workflows:
            del self.workflows[name]
            if self.current_workflow == name:
                self.current_workflow = list(self.workflows.keys())[0] if self.workflows else ""
            return True
        return False
        
    def get_workflow(self, name: str = None) -> Optional[dict]:
        """获取工作流配置"""
        name = name or self.current_workflow
        return self.workflows.get(name)
    
    def list_workflows(self) -> List[str]:
        """列出所有工作流名称"""
        return list(self.workflows.keys())
    
    def set_current_workflow(self, name: str) -> bool:
        """设置当前工作流"""
        if name in self.workflows:
            self.current_workflow = name
            return True
        return False


@dataclass
class UserConfig:
    """用户配置总类"""
    api_keys: APIKeyConfig = field(default_factory=APIKeyConfig)
    image_url: ImageURLConfig = field(default_factory=ImageURLConfig)
    google_drive: GoogleDriveConfig = field(default_factory=GoogleDriveConfig)
    comfyui: ComfyUIConfig = field(default_factory=ComfyUIConfig)
    output_dir: str = "./output"
    default_recognition_engine: str = ""  # 默认图像识别引擎
    default_generation_engine: str = ""   # 默认图生图引擎

    def save(self, path: Path = None):
        """保存配置到文件"""
        path = path or CONFIG_FILE

        # 确保配置目录存在
        path.parent.mkdir(parents=True, exist_ok=True)

        # 转换为可序列化的字典
        data = {
            "api_keys": asdict(self.api_keys),
            "image_url": asdict(self.image_url),
            "google_drive": asdict(self.google_drive),
            "comfyui": {
                "server_url": self.comfyui.server_url,
                "auth_username": self.comfyui.auth_username,
                "auth_password": self.comfyui.auth_password,
                "auth_server_url": self.comfyui.auth_server_url,
                "current_workflow": self.comfyui.current_workflow,
                "workflows": self.comfyui.workflows,
                "last_used": self.comfyui.last_used,
            },
            "output_dir": self.output_dir,
            "default_recognition_engine": self.default_recognition_engine,
            "default_generation_engine": self.default_generation_engine,
        }

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # 验证文件确实写入成功
        if not path.exists() or path.stat().st_size == 0:
            raise IOError(f"配置文件写入验证失败: {path}")
    
    @classmethod
    def load(cls, path: Path = None) -> 'UserConfig':
        """从文件加载配置"""
        path = path or CONFIG_FILE

        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            config = cls()

            # 加载API Keys
            if "api_keys" in data:
                for key, value in data["api_keys"].items():
                    if hasattr(config.api_keys, key):
                        setattr(config.api_keys, key, value)

            # 加载图片URL配置
            if "image_url" in data:
                for key, value in data["image_url"].items():
                    if hasattr(config.image_url, key):
                        setattr(config.image_url, key, value)

            # 加载 Google Drive 配置
            if "google_drive" in data:
                for key, value in data["google_drive"].items():
                    if hasattr(config.google_drive, key):
                        setattr(config.google_drive, key, value)

            # 加载ComfyUI配置
            if "comfyui" in data:
                comfyui_data = data["comfyui"]
                config.comfyui.server_url = comfyui_data.get("server_url", "")
                config.comfyui.auth_username = comfyui_data.get("auth_username", "")
                config.comfyui.auth_password = comfyui_data.get("auth_password", "")
                config.comfyui.auth_server_url = comfyui_data.get("auth_server_url", "")
                config.comfyui.current_workflow = comfyui_data.get("current_workflow", "")
                config.comfyui.workflows = comfyui_data.get("workflows", {})
                config.comfyui.last_used = comfyui_data.get("last_used", "")

            # 加载其他配置
            config.output_dir = data.get("output_dir", "./output")
            config.default_recognition_engine = data.get("default_recognition_engine", "")
            config.default_generation_engine = data.get("default_generation_engine", "")

            return config

        return cls()
    
    def validate(self) -> List[str]:
        """验证配置，返回错误列表"""
        errors = []
        
        if not self.api_keys.has_recognition_api():
            errors.append("请至少配置一个图像识别API")
        
        has_comfyui = bool(self.comfyui.get_effective_server_url())
        has_generation_api = self.api_keys.has_generation_api()
        
        if not has_generation_api and not has_comfyui:
            errors.append("请配置图生图API或ComfyUI服务器")
        
        return errors
    
    def is_configured(self) -> bool:
        """检查是否已完成基本配置"""
        return len(self.validate()) == 0
    
    def ensure_output_dir(self):
        """确保输出目录存在"""
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        Path(self.output_dir, "images").mkdir(exist_ok=True)
        Path(self.output_dir, "generated").mkdir(exist_ok=True)
        Path(self.output_dir, "competitor").mkdir(exist_ok=True)


# 全局配置实例
_config: Optional[UserConfig] = None


def get_config() -> UserConfig:
    """获取全局配置实例"""
    global _config
    if _config is None:
        _config = UserConfig.load()
    return _config


def reload_config():
    """重新加载配置"""
    global _config
    _config = UserConfig.load()
    return _config


def save_config():
    """保存全局配置"""
    global _config
    if _config is not None:
        _config.save()
