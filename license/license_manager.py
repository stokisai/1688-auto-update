"""
激活码管理模块 - 处理激活码验证、存储和检查

激活码算法：
- 激活码 = HMAC-SHA256(设备ID, SECRET_KEY)[:16]
- 激活信息加密存储到本地文件
"""

import json
import hmac
import hashlib
import base64
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from .device_fingerprint import get_device_id


# ==================== 密钥配置 ====================
# 重要：这个密钥用于生成激活码，请妥善保管
# 老师用这个密钥 + 设备ID 生成激活码
SECRET_KEY = "AI_BINDAO_2024_STOKIS_SECRET_KEY_V1"
# =================================================


class LicenseManager:
    """激活码管理器"""

    def __init__(self, app_data_dir: Optional[Path] = None):
        """
        初始化激活码管理器

        Args:
            app_data_dir: 应用数据目录，默认为用户目录下的 .ai_bindao
        """
        if app_data_dir is None:
            app_data_dir = Path.home() / ".ai_bindao"

        self.app_data_dir = app_data_dir
        self.license_file = app_data_dir / "license.dat"
        self._ensure_data_dir()

    def _ensure_data_dir(self):
        """确保数据目录存在"""
        self.app_data_dir.mkdir(parents=True, exist_ok=True)

    def get_device_id(self) -> str:
        """获取当前设备ID"""
        return get_device_id()

    def generate_license_key(self, device_id: str) -> str:
        """
        根据设备ID生成激活码（老师使用）

        Args:
            device_id: 设备ID

        Returns:
            str: 16位激活码
        """
        # 使用 HMAC-SHA256 生成激活码
        message = device_id.upper().encode('utf-8')
        key = SECRET_KEY.encode('utf-8')
        signature = hmac.new(key, message, hashlib.sha256).hexdigest()
        # 取前16位，转大写
        return signature[:16].upper()

    def verify_license_key(self, license_key: str) -> bool:
        """
        验证激活码是否正确

        Args:
            license_key: 用户输入的激活码

        Returns:
            bool: 是否验证通过
        """
        device_id = self.get_device_id()
        expected_key = self.generate_license_key(device_id)
        return license_key.upper().strip() == expected_key

    def activate(self, license_key: str, user_name: str = "") -> tuple[bool, str]:
        """
        激活软件

        Args:
            license_key: 激活码
            user_name: 用户名（可选）

        Returns:
            tuple: (是否成功, 消息)
        """
        if not self.verify_license_key(license_key):
            return False, "激活码无效，请检查后重试"

        # 保存激活信息
        license_data = {
            "device_id": self.get_device_id(),
            "license_key": license_key.upper().strip(),
            "user_name": user_name,
            "activated_at": datetime.now().isoformat(),
            "version": "1.1.0"
        }

        try:
            self._save_license_data(license_data)
            return True, "激活成功！"
        except Exception as e:
            return False, f"保存激活信息失败: {str(e)}"

    def is_activated(self) -> bool:
        """
        检查软件是否已激活

        Returns:
            bool: 是否已激活
        """
        license_data = self._load_license_data()
        if not license_data:
            return False

        # 验证设备ID是否匹配（防止复制激活文件）
        stored_device_id = license_data.get("device_id", "")
        current_device_id = self.get_device_id()

        if stored_device_id != current_device_id:
            return False

        # 验证激活码是否正确
        stored_key = license_data.get("license_key", "")
        return self.verify_license_key(stored_key)

    def get_license_info(self) -> Optional[Dict[str, Any]]:
        """
        获取激活信息

        Returns:
            dict: 激活信息，未激活返回None
        """
        if not self.is_activated():
            return None
        return self._load_license_data()

    def _save_license_data(self, data: Dict[str, Any]):
        """保存激活数据（简单加密）"""
        json_str = json.dumps(data, ensure_ascii=False)
        # 简单的 base64 编码 + 混淆
        encoded = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
        # 添加混淆前缀
        obfuscated = f"AIbindao_V1_{encoded}"

        with open(self.license_file, 'w', encoding='utf-8') as f:
            f.write(obfuscated)

    def _load_license_data(self) -> Optional[Dict[str, Any]]:
        """加载激活数据"""
        if not self.license_file.exists():
            return None

        try:
            with open(self.license_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()

            # 移除混淆前缀
            prefix = "AIbindao_V1_"
            if not content.startswith(prefix):
                return None

            content = content[len(prefix):]

            # 解码
            json_str = base64.b64decode(content.encode('utf-8')).decode('utf-8')
            return json.loads(json_str)
        except Exception:
            return None

    def deactivate(self) -> bool:
        """
        取消激活（删除激活文件）

        Returns:
            bool: 是否成功
        """
        try:
            if self.license_file.exists():
                self.license_file.unlink()
            return True
        except Exception:
            return False


# 单例实例
_license_manager: Optional[LicenseManager] = None


def get_license_manager() -> LicenseManager:
    """获取激活码管理器单例"""
    global _license_manager
    if _license_manager is None:
        _license_manager = LicenseManager()
    return _license_manager


def is_activated() -> bool:
    """快捷方法：检查是否已激活"""
    return get_license_manager().is_activated()


if __name__ == "__main__":
    # 测试
    manager = LicenseManager()
    device_id = manager.get_device_id()
    print(f"设备ID: {device_id}")
    print(f"激活码: {manager.generate_license_key(device_id)}")
    print(f"是否已激活: {manager.is_activated()}")
